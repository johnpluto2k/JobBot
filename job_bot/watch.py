"""Company posting watcher — poll the companies John tracks for NEW openings.

The tracker knows 200+ target companies but nothing was ever watching them; the
`jobs` table had not gained a row in over a month. This closes that loop: for every
company with a verified public job-board endpoint, fetch current postings, keep the
entry-level ones in range of the DMV, score them through the existing pipeline, and
insert only the ones not already seen.

Why this shape:

* **`jobs.url` is UNIQUE and `save_jobs()` is INSERT OR IGNORE**, so "what's new" is
  free — no content hashing, no separate seen-set. Re-polling a board inserts
  nothing unless a posting genuinely appeared.
* **Rows land with `site='<platform>'`**, which `applications.build_applications()`
  does not read (it takes only email/tracker/ledger). A posting John has not applied
  to therefore cannot leak into the applications funnel. That separation is
  deliberate — the funnel is what the coach trusts.
* **`next_check_due` is the work queue.** `companies.due_for_check()` and
  `mark_checked()` already exist and already spread companies over a 7-day cycle, so
  this schedules itself instead of inventing a second scheduler concept.

Only platforms with a public, unauthenticated JSON feed are supported: Greenhouse,
Ashby, SmartRecruiters, and Workday. Taleo, iCIMS, SuccessFactors and Phenom People
(which is Deloitte and EY) have no such feed and are left to the manual
`next_check_due` nudge — see job_bot/watch_registry.py.

CLI:
    python -m job_bot.watch --dry-run          # show what a pass would find
    python -m job_bot.watch --limit 5          # poll 5 due companies and save
    python -m job_bot.watch --all              # ignore next_check_due
"""
from __future__ import annotations

import re as _re
import time
from datetime import datetime

from . import companies
from .portals import (DEFAULT_KEYWORDS, _entry_level, _match, _requests,
                      _strip_html, _fetch_greenhouse)

# Be a polite client: these are other people's job boards.
INTER_COMPANY_DELAY_S = 0.6
HTTP_TIMEOUT_S = 20
USER_AGENT = "Mozilla/5.0 (compatible; JobBot/1.0; personal job search)"

# --- Location filter ---------------------------------------------------------
# portals.scan() has no location filter at all, which is why a live Stripe scan
# returns London, Dublin and Singapore roles. John is in the DC-Maryland-Virginia
# area and is not relocating abroad for an internship.
DMV_MARKERS = (
    "washington", "d.c.", "dc", "district of columbia", "maryland", "md",
    "virginia", "va", "baltimore", "arlington", "alexandria", "mclean", "reston",
    "tysons", "bethesda", "rockville", "silver spring", "columbia", "annapolis",
    "fairfax", "herndon", "vienna", "gaithersburg", "college park", "chevy chase",
    "germantown", "hyattsville", "greenbelt", "laurel", "towson", "mclean",
)
FOREIGN_MARKERS = (
    "india", "bengaluru", "bangalore", "hyderabad", "pune", "gurgaon", "noida",
    "london", "dublin", "singapore", "toronto", "vancouver", "canada", "poland",
    "warsaw", "manila", "philippines", "mexico", "germany", "berlin", "munich",
    "amsterdam", "netherlands", "sydney", "australia", "tokyo", "japan",
    "shanghai", "beijing", "china", "korea", "seoul", "brazil", "argentina",
    "spain", "madrid", "barcelona", "paris", "france", "israel", "tel aviv",
    "united kingdom", "ireland", "sweden", "stockholm", "zurich", "switzerland",
    "costa rica", "colombia", "romania", "bucharest", "portugal", "lisbon",
    "mumbai", "delhi", "chennai", "kolkata", "gurugram", "ahmedabad",
    "hong kong", "taipei", "kuala lumpur", "jakarta", "bangkok", "dubai",
    "cairo", "johannesburg", "nairobi", "santiago", "lima", "bogota",
    "sao paulo", "buenos aires", "montreal", "ottawa", "calgary", "edinburgh",
    "manchester", "glasgow", "milan", "rome", "prague", "budapest", "athens",
    "oslo", "copenhagen", "helsinki", "brussels", "luxembourg", "geneva",
)

# Markers are matched on WORD BOUNDARIES, not as substrings. Two-letter state
# codes are the whole reason: a plain `"va" in location` check accepted
# "Mumbai Shivaji Park" (shi-VA-ji), which is the same substring bug that let
# "EY" match "Morgan Stanley" in the email classifier.
_DMV_RE = _re.compile(r"\b(?:" + "|".join(_re.escape(m) for m in DMV_MARKERS) + r")\b", _re.I)
_FOREIGN_RE = _re.compile(r"\b(?:" + "|".join(_re.escape(m) for m in FOREIGN_MARKERS) + r")\b", _re.I)
_NATIONAL = {"united states", "us", "usa", "u s", "nationwide", "multiple locations"}


def location_ok(location: str, dmv_only: bool = True) -> bool:
    """True if a posting is somewhere John could actually take the job.

    Blank locations are kept - a missing field is not evidence of a bad location,
    and dropping them would silently hide most Workday rows.
    """
    low = (location or "").strip().lower()
    if not low:
        return True
    # Foreign check comes FIRST. "Toronto, Remote-Canada" contains "remote" but is
    # not a job John can take, and an early remote check used to let it through.
    if _FOREIGN_RE.search(low):
        return False
    if "remote" in low or "anywhere" in low:
        return True
    if not dmv_only:
        return True
    if _DMV_RE.search(low):
        return True
    return low.replace(".", "").replace(",", "").strip() in _NATIONAL


# --- Fetchers ----------------------------------------------------------------
def _fetch_ashby(token: str, keywords: list[str]) -> list[dict]:
    """Ashby's public job board (GraphQL, no auth).

    This is the GRC-tech lane - Vanta, Drata, Secureframe, Numeric - which is the
    most on-target group in the whole tracker for IT Audit / Technology Risk.
    """
    req = _requests()
    if not req:
        return []
    query = ("query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) "
             "{ jobBoard: jobBoardWithTeams(organizationHostedJobsPageName: "
             "$organizationHostedJobsPageName) { jobPostings { id title locationName "
             "employmentType } } }")
    try:
        r = req.post(
            "https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams",
            json={"operationName": "ApiJobBoardWithTeams",
                  "variables": {"organizationHostedJobsPageName": token},
                  "query": query},
            headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT_S)
        if r.status_code != 200:
            return []
        board = ((r.json() or {}).get("data") or {}).get("jobBoard") or {}
    except Exception:
        return []
    rows = []
    for j in board.get("jobPostings") or []:
        title = j.get("title") or ""
        if not _match(title, keywords) or not _entry_level(title):
            continue
        rows.append({
            "title": title,
            "location": j.get("locationName") or "",
            "url": f"https://jobs.ashbyhq.com/{token}/{j.get('id')}",
            "site": "ashby", "date_posted": "", "description": "",
        })
    return rows


def _fetch_smartrecruiters(token: str, keywords: list[str]) -> list[dict]:
    """SmartRecruiters postings API.

    Careful: this returns HTTP 200 with totalFound=0 for ANY token, real or not,
    so a 200 is not evidence the board exists. Only a positive totalFound is.
    """
    req = _requests()
    if not req:
        return []
    try:
        r = req.get(f"https://api.smartrecruiters.com/v1/companies/{token}/postings",
                    params={"limit": 100}, headers={"User-Agent": USER_AGENT},
                    timeout=HTTP_TIMEOUT_S)
        if r.status_code != 200:
            return []
        data = r.json() or {}
    except Exception:
        return []
    if not data.get("totalFound"):
        return []
    rows = []
    for j in data.get("content") or []:
        title = j.get("name") or ""
        if not _match(title, keywords) or not _entry_level(title):
            continue
        loc = j.get("location") or {}
        where = ", ".join(x for x in (loc.get("city"), loc.get("region")) if x)
        rows.append({
            "title": title, "location": where,
            "url": f"https://jobs.smartrecruiters.com/{token}/{j.get('id')}",
            "site": "smartrecruiters", "date_posted": (j.get("releasedDate") or "")[:10],
            "description": "",
        })
    return rows


# Some Workday tenants leave locationsText empty and append the location to the
# title instead ("Customer Account Associate | Memphis, TN"). Without this, those
# postings look location-less, and location_ok() keeps unknown locations - so a
# single tenant flooded the pipeline with 95 out-of-area roles.
_TITLE_LOCATION_RE = _re.compile(r"\|\s*([^|]{2,40}?)\s*$")
_CITY_STATE_RE = _re.compile(r",\s*[A-Z]{2}\b")


def _location_from_title(title: str) -> str:
    tail = _TITLE_LOCATION_RE.search(title or "")
    if not tail:
        return ""
    candidate = tail.group(1).strip()
    if _CITY_STATE_RE.search(candidate) or _DMV_RE.search(candidate) or _FOREIGN_RE.search(candidate):
        return candidate
    return ""


def _fetch_workday(host: str, tenant: str, site: str, keywords: list[str],
                   max_pages: int = 5) -> list[dict]:
    """Workday's CXS endpoint - public JSON, no auth.

    Worth having even though it is the fiddliest: Workday is where the Big 4 and
    govcon employers actually live (PwC, Booz Allen, Guidehouse, Capital One,
    Leidos, Northrop). `postedOn` is a relative string ("Posted 30+ Days Ago"),
    so freshness comes from URL dedupe, not from that field.
    """
    req = _requests()
    if not req:
        return []
    rows, seen = [], set()
    endpoint = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    for kw in keywords[:4]:  # a few targeted searches beats pulling the whole board
        for page in range(max_pages):
            try:
                r = req.post(endpoint,
                             json={"appliedFacets": {}, "limit": 20,
                                   "offset": page * 20, "searchText": kw},
                             headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                             timeout=HTTP_TIMEOUT_S)
                if r.status_code != 200:
                    break
                data = r.json() or {}
            except Exception:
                break
            postings = data.get("jobPostings") or []
            if not postings:
                break
            for j in postings:
                title = j.get("title") or ""
                path = j.get("externalPath") or ""
                if not path or path in seen:
                    continue
                # Re-check the keyword here rather than trusting searchText. Some
                # tenants ignore it and return their entire board: Raymond James
                # answered all four searches with the same 102 rows, which then
                # arrived as 95 unrelated postings. The other three fetchers all
                # filter on the title, so this keeps them consistent.
                if not _match(title, keywords) or not _entry_level(title):
                    continue
                seen.add(path)
                rows.append({
                    "title": title,
                    "location": j.get("locationsText") or _location_from_title(title),
                    "url": f"https://{host}/en-US/{site}{path}",
                    "site": "workday", "date_posted": "", "description": "",
                })
            if len(postings) < 20:
                break
            time.sleep(0.3)
    return rows


FETCHERS = {
    "Greenhouse": lambda c, kw: _fetch_greenhouse(c["ats_token"], kw),
    "Ashby": lambda c, kw: _fetch_ashby(c["ats_token"], kw),
    "SmartRecruiters": lambda c, kw: _fetch_smartrecruiters(c["ats_token"], kw),
    "Workday": lambda c, kw: _fetch_workday(c["ats_host"], c["ats_tenant"],
                                            c["ats_site"], kw),
}


# --- One company -------------------------------------------------------------
def watch_company(company: dict, keywords: list[str] | None = None,
                  save: bool = True, dmv_only: bool = True) -> dict:
    """Poll one company. Never raises - a dead board must not kill the pass."""
    kw = keywords or DEFAULT_KEYWORDS
    name = company.get("name")
    platform = (company.get("ats_platform") or "").strip()
    result = {"company": name, "platform": platform, "found": 0, "in_range": 0,
              "new": 0, "error": None}

    fetch = FETCHERS.get(platform)
    if not fetch:
        result["error"] = f"no fetcher for platform {platform!r}"
        return result
    try:
        rows = fetch(company, kw)
    except Exception as exc:  # noqa: BLE001 - deliberately broad, see docstring
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    result["found"] = len(rows)
    rows = [r for r in rows if location_ok(r.get("location", ""), dmv_only)]
    result["in_range"] = len(rows)
    for r in rows:
        r["company"] = name

    if not save or not rows:
        result["rows"] = rows
        return result

    try:
        from .deprecated.jobsearch import save_jobs, score_and_route

        # score_and_route needs the master profile to compute the ATS score.
        # _profile() caches it for the process - see the note there.
        scored = score_and_route(rows, _profile(), drop_senior=True)
        result["new"] = save_jobs(scored)
        _attach_company_id(company.get("id"), [r.get("url") for r in scored])
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"save failed: {type(exc).__name__}: {exc}"
    result["rows"] = rows
    return result


_PROFILE_CACHE: dict | None = None


def _profile() -> dict:
    """Master profile for ATS scoring, loaded once per process.

    load_profile() re-reads and re-parses master_profile.json on every call, and a
    full pass scores hundreds of postings across dozens of companies.
    """
    global _PROFILE_CACHE
    if _PROFILE_CACHE is None:
        from .ats_engine import load_profile

        _PROFILE_CACHE = load_profile(None)
    return _PROFILE_CACHE


def _attach_company_id(company_id: int | None, urls: list[str]) -> None:
    """Link saved postings back to the tracked company.

    save_jobs() does not set company_id, but the watcher always knows which
    company it polled - so the FK finally means something and per-company
    rollups ("3 new roles at Appian") become possible.
    """
    urls = [u for u in urls if u]
    if not company_id or not urls:
        return
    from .db import connect

    con = connect()
    try:
        for i in range(0, len(urls), 400):
            chunk = urls[i:i + 400]
            con.execute(
                "UPDATE jobs SET company_id=? WHERE company_id IS NULL AND url IN (%s)"
                % ",".join("?" * len(chunk)), (company_id, *chunk))
        con.commit()
    finally:
        con.close()


# --- A full pass -------------------------------------------------------------
def watched_companies(only_due: bool = True) -> list[dict]:
    rows = [c for c in companies.list_all() if c.get("watch_enabled")]
    if not only_due:
        return rows
    due_ids = {c["id"] for c in companies.due_for_check()}
    return [c for c in rows if c["id"] in due_ids]


def run(limit: int | None = None, only_due: bool = True, save: bool = True,
        dmv_only: bool = True) -> dict:
    """Poll due watched companies. Returns a summary; never raises."""
    targets = watched_companies(only_due=only_due)
    if limit:
        targets = targets[:limit]

    started = datetime.now().isoformat(timespec="seconds")
    results, total_new = [], 0
    for i, c in enumerate(targets):
        res = watch_company(c, save=save, dmv_only=dmv_only)
        results.append(res)
        total_new += res.get("new", 0)
        if save:
            try:
                companies.update(c["id"], last_watch_at=started,
                                 last_watch_new=res.get("new", 0),
                                 last_watch_error=res.get("error"))
                if not res.get("error"):
                    companies.mark_checked(c["id"], next_check_in_days=7)
            except Exception:
                pass
        if i < len(targets) - 1:
            time.sleep(INTER_COMPANY_DELAY_S)

    return {
        "started_at": started,
        "checked": len(results),
        "new_postings": total_new,
        "results": results,
        "errors": [r for r in results if r.get("error")],
    }


def run_if_due() -> dict | None:
    """Scheduler entry point. Swallows everything - APScheduler must never see a raise."""
    try:
        out = run(only_due=True, save=True)
    except Exception:
        return None
    # notify.py was complete but orphaned - nothing imported it, so the
    # notifications table held 5 stale rows and no alert had fired in months. A
    # pass that found new postings is exactly when it should speak up. It dedupes
    # on the job URL itself, so re-running can never double-ping.
    if out and out.get("new_postings"):
        try:
            from . import notify

            notify.run()
        except Exception:
            pass
    return out


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Poll tracked companies for new postings")
    ap.add_argument("--limit", type=int, default=None, help="max companies this pass")
    ap.add_argument("--all", action="store_true", help="ignore next_check_due")
    ap.add_argument("--dry-run", action="store_true", help="fetch but do not save")
    ap.add_argument("--anywhere", action="store_true", help="skip the DMV location filter")
    args = ap.parse_args()

    out = run(limit=args.limit, only_due=not args.all, save=not args.dry_run,
              dmv_only=not args.anywhere)
    print(f"checked {out['checked']} companies, {out['new_postings']} new postings")
    for r in out["results"]:
        flag = f"  ! {r['error']}" if r.get("error") else ""
        print(f"  {r['company']:<28} {r['platform']:<16} "
              f"found={r['found']:<4} in_range={r['in_range']:<4} new={r['new']}{flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
