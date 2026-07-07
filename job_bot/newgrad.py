"""New-grad / entry-level job tracker (inspired by newgrad-jobs.com).

newgrad-jobs.com is an Airtable-backed aggregator of LinkedIn / Indeed /
Handshake postings filtered to 0–2 years of experience. Rather than scrape their
signed Airtable views (fragile + ToS grey area), this module reproduces the
*intent* robustly: it runs entry-level searches for John's target roles across
the same underlying boards via the existing JobSpy pipeline, then scores them
against his profile, routes by market tier, dedupes, and stores them — so they
flow into the Action Center, priority ranking, and the notification system.

Run it on a schedule (Task Scheduler / cron / a Claude cron task) and the
`notify` module will alert on the fresh, high-priority matches.
"""

from __future__ import annotations

from .ats_engine import load_profile
from .jobsearch import save_jobs, score_and_route, search

# John's two active searches (he graduates May 2027):
#   1) REMOTE internships he can do during Fall 2026 / Spring 2027 (part-time-friendly,
#      remote so they fit around classes), and
#   2) FULL-TIME new-grad roles starting Summer 2027.
# Each entry: (search term, remote-only?). Kept tight so a run isn't a huge scrape.

# Remote Fall/Spring internships — searched remote-only (is_remote=True).
INTERNSHIP_QUERIES: list[tuple[str, bool]] = [
    ("IT audit intern", True),
    ("technology risk intern", True),
    ("audit intern", True),
    ("data analyst intern", True),
    ("accounting intern", True),
    ("business analyst intern", True),
    ("finance intern", True),
]

# Full-time, Summer-2027-start / new-grad roles. Most searched broadly (DMV + remote);
# data/analyst roles flagged remote-friendly.
FULLTIME_QUERIES: list[tuple[str, bool]] = [
    ("IT audit associate", False),
    ("technology risk analyst", False),
    ("audit associate new grad", False),
    ("business analyst new grad", False),
    ("data analyst", True),
    ("financial analyst new grad", False),
    ("risk advisory consultant", False),
]

# Combined default: both searches run together so the pipeline + Action Center
# surface remote internships AND Summer 2027 full-time in one pass.
TARGET_QUERIES: list[tuple[str, bool]] = INTERNSHIP_QUERIES + FULLTIME_QUERIES

DEFAULT_LOCATION = "Washington, DC"

# --- Career tracks -----------------------------------------------------------
# Role search terms grouped by track so John can widen beyond business/finance into
# data and *tech* (his second major is Information Science). Each term carries a
# remote-friendly flag used for full-time searches; internships are searched
# remote-first (they fit around classes) unless the caller says otherwise.
TRACKS: dict[str, list[tuple[str, bool]]] = {
    "Accounting & Audit": [
        ("audit", False), ("IT audit", False), ("internal audit", False),
        ("assurance associate", False), ("tax", False), ("accounting", False)],
    "Finance & FP&A": [
        ("financial analyst", False), ("FP&A", False), ("finance", False),
        ("investment", False)],
    "Data & Analytics": [
        ("data analyst", True), ("business analyst", False), ("data scientist", True),
        ("business intelligence", True), ("analytics", True)],
    "IT & Cybersecurity": [
        ("technology risk", False), ("IT auditor", False), ("cybersecurity analyst", False),
        ("information security", False), ("GRC analyst", False), ("IT risk", False)],
    "Software & Engineering": [
        ("software engineer", False), ("software developer", False),
        ("full stack developer", False), ("backend engineer", False),
        ("data engineer", True), ("cloud engineer", False), ("systems analyst", False),
        ("IT support", False)],
    "Consulting": [
        ("consulting analyst", False), ("management consultant", False),
        ("risk advisory consultant", False), ("strategy analyst", False),
        ("advisory associate", False)],
    "Marketing & Communications": [
        ("marketing analyst", False), ("marketing coordinator", False),
        ("communications specialist", False), ("content marketing", True),
        ("social media coordinator", True)],
    "Operations & Supply Chain": [
        ("operations analyst", False), ("supply chain analyst", False),
        ("logistics analyst", False), ("procurement analyst", False)],
    "Human Resources": [
        ("HR coordinator", False), ("human resources analyst", False),
        ("talent acquisition coordinator", False), ("people operations analyst", True)],
}

DEFAULT_TRACKS = ["Accounting & Audit", "IT & Cybersecurity", "Data & Analytics"]


def build_track_queries(tracks: list[str], kind: str,
                        remote_internships: bool = True) -> list[tuple[str, bool]]:
    """Turn selected tracks into (search_term, is_remote) pairs for `kind`
    ('internship' or 'fulltime'). Internships get an ' intern' suffix and are
    remote-first by default; full-time uses each term's own remote flag."""
    out: list[tuple[str, bool]] = []
    seen: set[str] = set()
    for t in tracks:
        for term, remote in TRACKS.get(t, []):
            if kind == "internship":
                q, rflag = f"{term} intern", remote_internships
            else:
                q, rflag = term, remote
            if q.lower() not in seen:
                seen.add(q.lower())
                out.append((q, rflag))
    return out


# --- Hiring cycles (derived from graduation date) ----------------------------
from datetime import date as _date, datetime as _datetime

_SEASON_STARTS = [("Spring", 1), ("Summer", 5), ("Fall", 9)]


def parse_grad_date(s: str | None) -> _date:
    """Parse a graduation string like 'May 2027' into the 1st of that month."""
    s = (s or "").strip()
    for fmt in ("%B %Y", "%b %Y", "%m/%Y", "%Y-%m-%d", "%Y-%m", "%B %d, %Y"):
        try:
            return _datetime.strptime(s, fmt).date().replace(day=1)
        except ValueError:
            continue
    try:
        return _date(int(s), 5, 1)  # bare year -> a May graduation
    except (ValueError, TypeError):
        return _date(_date.today().year + 1, 5, 1)


def available_cycles(grad_date: _date, today: _date | None = None) -> list[dict]:
    """Upcoming hiring cycles relevant to a student graduating on `grad_date`.

    Seasons before graduation are internships; the graduation season and the one
    after are full-time (new grad). Only cycles you'd realistically apply to now
    (starting in the future, within ~14 months) are returned, soonest first.
    """
    today = today or _date.today()
    grad_start = grad_date.replace(day=1)
    this_month = today.replace(day=1)

    cand: list[tuple[str, int, _date]] = []
    for y in range(today.year, today.year + 3):
        for name, m in _SEASON_STARTS:
            cand.append((name, y, _date(y, m, 1)))
    cand.sort(key=lambda x: x[2])

    cycles: list[dict] = []
    for name, y, start in cand:
        if start < this_month or (start - today).days > 430:
            continue
        if start < grad_start:
            kind, label = "internship", f"{name} {y} · Internship"
        else:
            kind, label = "fulltime", f"{name} {y} · Full-time (new grad)"
        cycles.append({"key": f"{name.lower()}-{y}-{kind}", "season": name, "year": y,
                       "kind": kind, "label": label, "start": start.isoformat()})
    return cycles


def run(location: str = DEFAULT_LOCATION, hours_old: int = 72, results_per: int = 12,
        sites: list[str] | None = None, queries: list[tuple[str, bool]] | None = None,
        profile: dict | None = None) -> dict:
    """Search every target query, score+route, dedupe, and persist. Returns a summary."""
    profile = profile or load_profile(None)
    queries = queries or TARGET_QUERIES
    seen_urls: set[str] = set()
    all_rows: list[dict] = []
    per_query: list[dict] = []

    for term, remote in queries:
        rows = search(term, location=location, sites=sites, results=results_per,
                      hours_old=hours_old, is_remote=remote)
        fresh = [r for r in rows if r.get("url") and r["url"] not in seen_urls]
        for r in fresh:
            seen_urls.add(r["url"])
            r["search_term"] = term
        all_rows.extend(fresh)
        per_query.append({"term": term, "found": len(rows), "new": len(fresh)})
        print(f"  · {term:<38} found {len(rows):>3}  new {len(fresh):>3}")

    if not all_rows:
        print("\n  No postings returned (JobSpy unavailable, rate-limited, or no matches).")
        return {"scraped": 0, "saved": 0, "per_query": per_query, "top": []}

    scored = score_and_route(all_rows, profile)
    saved = save_jobs(scored)
    top = sorted(scored, key=lambda x: x["priority"], reverse=True)[:10]
    return {"scraped": len(all_rows), "saved": saved, "per_query": per_query,
            "top": top, "scored": scored}


def main() -> None:
    import argparse
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Job tracker for John's roles: remote "
                                 "Fall/Spring internships + Summer 2027 full-time.")
    ap.add_argument("--location", default=DEFAULT_LOCATION)
    ap.add_argument("--hours", type=int, default=72, help="Only postings newer than N hours")
    ap.add_argument("--results", type=int, default=12, help="Results per query")
    ap.add_argument("--sites", help="Comma-separated: indeed,linkedin,glassdoor,google,zip_recruiter")
    ap.add_argument("--mode", choices=["all", "internship", "fulltime"], default="all",
                    help="Which search to run: remote internships, Summer-2027 full-time, or both")
    args = ap.parse_args()
    sites = [s.strip() for s in args.sites.split(",")] if args.sites else None
    queries = {"internship": INTERNSHIP_QUERIES, "fulltime": FULLTIME_QUERIES,
               "all": TARGET_QUERIES}[args.mode]

    label = {"internship": "remote Fall/Spring internships",
             "fulltime": "Summer 2027 full-time / new-grad roles",
             "all": "remote internships + Summer 2027 full-time"}[args.mode]
    print(f"\nTracking {label} near {args.location} (+ remote) (< {args.hours}h old):")
    res = run(location=args.location, hours_old=args.hours, results_per=args.results,
              sites=sites, queries=queries)
    print(f"\nScraped {res['scraped']} unique postings, saved {res['saved']} new to the pipeline.")
    if res["top"]:
        print("\nTop matches by priority:")
        for r in res["top"]:
            print(f"  {r['priority']:>4.0f}  ATS {r.get('ats_score',0):>4.0f}  "
                  f"{(r.get('company') or '?')[:20]:<20} {(r.get('title') or '')[:40]}")
    print("\nThese now appear in the dashboard pipeline + Action Center. Run "
          "`python -m job_bot.notify` to get alerted on the freshest high-priority ones.")


if __name__ == "__main__":
    main()
