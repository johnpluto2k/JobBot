"""Phase 5: job ingestion via JobSpy (LinkedIn, Indeed, Glassdoor, Google,
ZipRecruiter), with routing + optional ATS scoring.

JobSpy is optional: if it (or network access) is unavailable, search() returns
an empty list with a clear message — the routing logic is still usable on
manually supplied postings.

NOTE on scraping posture: this is personal-use, low-volume, UNAUTHENTICATED
scraping (no LinkedIn login cookie — authenticated scraping would tie the risk
to the account rather than an IP). Indeed tolerates this well; LinkedIn
throttles (~10 result pages per IP → 429s) and periodically breaks scrapers
when its page structure changes. Defaults are therefore Indeed-first with
LinkedIn opt-in, one backoff retry on rate limits, and a scrape log that skips
re-running the same search within an hour. Not a basis for scaling up request
volume later.
"""

from __future__ import annotations

import time
from datetime import date, datetime

from ..db import connect

DEFAULT_SITES = ["indeed"]          # LinkedIn is opt-in (see module note)
RESCRAPE_WINDOW_MIN = 60            # identical search within this window → skip
RATE_LIMIT_WAIT_S = 45              # backoff before the single retry on a 429
INTER_SITE_DELAY_S = 3              # pause between sites in a multi-site search


def _jobspy_available() -> bool:
    try:
        import jobspy  # noqa: F401
        return True
    except Exception:
        return False


def _recent_scrape(term: str, location: str) -> str | None:
    """Return the timestamp of a scrape of this term+location inside the
    re-scrape window, or None."""
    try:
        con = connect()
        row = con.execute(
            "SELECT scraped_at FROM scrape_log WHERE term = ? AND location = ? "
            "AND scraped_at > datetime('now', ?) ORDER BY scraped_at DESC LIMIT 1",
            (term, location, f"-{RESCRAPE_WINDOW_MIN} minutes")).fetchone()
        con.close()
        return row["scraped_at"] if row else None
    except Exception:
        return None


def _log_scrape(term: str, location: str, sites: list[str], n: int) -> None:
    try:
        con = connect()
        con.execute("INSERT INTO scrape_log (term, location, sites, results) "
                    "VALUES (?,?,?,?)", (term, location, ",".join(sites), n))
        con.commit()
        con.close()
    except Exception:
        pass


def _looks_rate_limited(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(s in msg for s in ("429", "rate limit", "rate-limit",
                                  "too many requests", "throttl"))


def _scrape_site(site: str, term: str, location: str, results: int,
                 hours_old: int | None, is_remote: bool) -> list[dict]:
    """Scrape one site, with a single backoff retry on a rate-limit-shaped error."""
    from jobspy import scrape_jobs

    for attempt in (1, 2):
        try:
            df = scrape_jobs(
                site_name=[site], search_term=term,
                location=location or "United States",
                results_wanted=results, hours_old=hours_old, is_remote=is_remote,
                country_indeed="USA",
            )
            break
        except Exception as exc:
            if attempt == 1 and _looks_rate_limited(exc):
                print(f"  ! {site} rate-limited ({exc}); retrying once in "
                      f"{RATE_LIMIT_WAIT_S}s ...")
                time.sleep(RATE_LIMIT_WAIT_S)
                continue
            print(f"  ! {site} scrape failed ({exc}). Try fewer sites/results "
                  "or check the network.")
            return []

    rows: list[dict] = []
    for _, r in df.iterrows():
        rows.append({
            "title": _s(r.get("title")),
            "company": _s(r.get("company")),
            "location": _s(r.get("location")),
            "site": _s(r.get("site")),
            "url": _s(r.get("job_url")),
            "date_posted": _s(r.get("date_posted")),
            "description": _s(r.get("description")),
        })
    return rows


def search(term: str, location: str = "", sites: list[str] | None = None,
           results: int = 20, hours_old: int | None = None,
           is_remote: bool = False, force: bool = False) -> list[dict]:
    """Scrape postings. Returns normalized dicts; [] if JobSpy unavailable.

    Re-running the same term+location within RESCRAPE_WINDOW_MIN warns and
    skips (pass force=True to override). Sites are scraped one at a time with
    a small delay in between so a multi-site search doesn't hammer anyone.
    """
    if not _jobspy_available():
        print("  ! JobSpy not installed/importable — skipping live scrape.")
        return []

    sites = sites or list(DEFAULT_SITES)

    if not force:
        when = _recent_scrape(term, location)
        if when:
            print(f"  · skipped '{term}' — already scraped at {when} UTC "
                  f"(< {RESCRAPE_WINDOW_MIN} min ago). Use force/--force to re-run.")
            return []

    rows: list[dict] = []
    for i, site in enumerate(sites):
        if i > 0:
            time.sleep(INTER_SITE_DELAY_S)
        rows.extend(_scrape_site(site, term, location, results, hours_old, is_remote))

    _log_scrape(term, location, sites, len(rows))
    return rows


def _s(v) -> str:
    if v is None:
        return ""
    try:
        import math
        if isinstance(v, float) and math.isnan(v):
            return ""
    except Exception:
        pass
    return str(v).strip()


def _days_since(date_posted: str) -> int | None:
    if not date_posted:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            d = datetime.strptime(date_posted[:19], fmt).date()
            return max(0, (date.today() - d).days)
        except ValueError:
            continue
    return None


def score_and_route(rows: list[dict], profile: dict, score_each: bool = True,
                    drop_senior: bool = True) -> list[dict]:
    """Attach market tier, ATS score, priority, legitimacy, seniority, and qualification gaps to each row.

    By default `drop_senior=True` filters out senior/lead/exec roles — the pipeline
    is aimed at John's level (internships + entry-level), so senior postings never
    reach it. Set drop_senior=False to keep them (tagged, not applied).

    Also checks for certification/degree gaps and applies a penalty score.
    """
    from ..ats_engine import score
    from ..jd_parser import parse_jd
    from ..legitimacy import assess
    from ..applications import classify_field
    from ..routing import route
    from ..seniority import classify as sen_classify, too_senior
    from ..qualifications import check_qualifications

    out: list[dict] = []
    for row in rows:
        days = _days_since(row.get("date_posted", ""))
        ats = 0.0
        job = None
        if score_each and row.get("description"):
            job = parse_jd(row["description"], url=row.get("url"), use_llm=False)
            job.company = job.company or row.get("company")
            job.location = job.location or row.get("location")
            ats = score(job, profile).overall_score
        if job is None:
            from .jd_models import JobPosting
            job = JobPosting(title=row.get("title"), company=row.get("company"),
                             location=row.get("location"), source_url=row.get("url"),
                             raw_text=row.get("description", ""))
        # Seniority: read the level off the title + JD; skip anything above John's level.
        sen = sen_classify(row.get("title"), row.get("description", ""),
                           getattr(job, "years_experience", None))
        if drop_senior and too_senior(sen):
            continue
        # Field fit: a role outside John's target fields ('Other') is not a clean apply.
        on_target = classify_field(row.get("title") or "") != "Other"
        # Legitimacy check (career-ops Block G) feeds the apply gate in route().
        legit = assess(row.get("description", ""), title=row.get("title"),
                       company=row.get("company"), days_since=days)
        # Qualification gaps: check for required/preferred certs or degrees John lacks.
        qual = check_qualifications(row.get("description", ""))
        r = route(job, ats, days, legit_score=legit.legit_score, seniority=sen,
                  on_target=on_target)
        # Apply qualification penalty to priority (down-rank if certs/degrees missing)
        r["priority"] = max(0, r.get("priority", 0) - qual.get("penalty_score", 0))
        out.append({**row, "ats_score": round(ats, 1), **r, "days_since": days,
                    "legit_score": legit.legit_score, "legit_grade": legit.grade,
                    "legit_flags": legit.summary(),
                    "qual_verdict": qual.get("verdict"),
                    "qual_certs_missing": qual.get("certs_missing"),
                    "qual_degree_gap": qual.get("degree_gap")})
    out.sort(key=lambda x: x["priority"], reverse=True)
    return out


def save_jobs(rows: list[dict]) -> int:
    con = connect()
    n = 0
    fails = 0
    for r in rows:
        try:
            # Try to save with qualification fields; fall back if column doesn't exist
            qual_certs = ",".join(r.get("qual_certs_missing", []))
            qual_degree = r.get("qual_degree_gap", "")
            try:
                cur = con.execute(
                    "INSERT OR IGNORE INTO jobs (title, company, location, site, url, "
                    "date_posted, market_tier, tier_num, ats_score, priority, description, "
                    "legit_score, legit_grade, legit_flags, recommendation, seniority, "
                    "qual_verdict, qual_certs_missing, qual_degree_gap) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (r.get("title"), r.get("company"), r.get("location"), r.get("site"),
                     r.get("url"), r.get("date_posted"), r.get("market_tier"), r.get("tier_num"),
                     r.get("ats_score"), r.get("priority"), (r.get("description") or "")[:8000],
                     r.get("legit_score"), r.get("legit_grade"), r.get("legit_flags"),
                     r.get("recommendation"), r.get("seniority"),
                     r.get("qual_verdict", ""), qual_certs, qual_degree),
                )
            except Exception:
                # Fallback: save without qual fields (older schema)
                cur = con.execute(
                    "INSERT OR IGNORE INTO jobs (title, company, location, site, url, "
                    "date_posted, market_tier, tier_num, ats_score, priority, description, "
                    "legit_score, legit_grade, legit_flags, recommendation, seniority) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (r.get("title"), r.get("company"), r.get("location"), r.get("site"),
                     r.get("url"), r.get("date_posted"), r.get("market_tier"), r.get("tier_num"),
                     r.get("ats_score"), r.get("priority"), (r.get("description") or "")[:8000],
                     r.get("legit_score"), r.get("legit_grade"), r.get("legit_flags"),
                     r.get("recommendation"), r.get("seniority")),
                )
            # `con.total_changes` is cumulative for the whole connection, so once a
            # single row inserted it stayed truthy forever and every subsequent row
            # counted as "saved" even when INSERT OR IGNORE ignored it as a dupe.
            # The UI's "saved N to pipeline" was meaningless. Count the real row.
            n += 1 if cur.rowcount == 1 else 0
        except Exception:
            fails += 1
    if fails:
        print(f"  ! save_jobs: {fails}/{len(rows)} rows failed to insert "
              "(schema mismatch?)")
    con.commit()
    con.close()
    return n
