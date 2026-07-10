"""Jobright.ai as a job source — pull your AI-matched recommendations into the
pipeline, scored/routed/legitimacy-checked like every other source.

Jobright is login-walled and personalized, so this reads YOUR authenticated
session — nothing here handles or stores your password. Two auth paths (pick one
in `run()`), both keeping the session token out of the codebase:

  1. Cookie  — export your jobright session cookie once into the gitignored .env
               as `JOBRIGHT_COOKIE=...`; this hits the JSON API directly with it.
               Lightest, but the cookie expires (re-export periodically).
  2. Playwright — drive a logged-in browser profile (you sign in once; the
               session persists in the profile). Robust to the quirks below;
               the token never leaves the browser. See `fetch_via_playwright`.

Reverse-engineered 2026-07-05 from the live app (schema confirmed; a few value
formats are marked VERIFY — nail them against one live sample when you wire auth):

  GET https://jobright.ai/swan/recommend/list/jobs
      ?refresh=<bool>&sortCondition=0&position=<offset>&count=<n>&syncRerank=false
  -> { success, errorCode(10000=ok), errorMsg, result: [ item, ... ] }
     item.displayScore                      # jobright's match % (0-100)
     item.jobResult    { jobId, jobTitle, jobNlpTitle, jobSeniority, jobLocation,
                         jobLocations, isRemote, workModel, publishTime,
                         publishTimeDesc, salaryDesc, minSalary, ... }
     item.companyResult{ companyId, companyName, companySize, companyDesc,
                         companyCategories, companyURL, companyLinkedinURL,
                         companyFoundYear, companyLocation, fundraisingCurrentStage }

GOTCHA: the recommend feed is STATEFUL — `position=0` on a cold call returns an
empty `result`; the UI seeds the feed then pages with position=10,20,… So we
start with `refresh=true` and stop as soon as a page comes back empty.

CLI:
    python -m job_bot.jobright --preview          # fetch + parse, print, don't save
    python -m job_bot.jobright --save             # score/route + write to the jobs table
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from . import config  # noqa: F401 — importing config loads .env (JOBRIGHT_COOKIE)

API_BASE = "https://jobright.ai/swan/recommend/list/jobs"
# Per-job permalink used as the UNIQUE dedupe key in the jobs table.
# VERIFY the exact path against a real job (jobright uses /jobs/info/<id>); even
# if the display path differs, this stays a stable per-job unique key.
JOB_URL_FMT = "https://jobright.ai/jobs/info/{job_id}"
SITE = "jobright"
RECOMMEND_URL = "https://jobright.ai/jobs/recommend"
# Persistent Playwright profile — you log in here ONCE (headed), the session
# then lives in this dir and later headless runs reuse it. Never holds your
# password; it's the same on-disk session store a normal browser keeps.
PROFILE_DIR = config.OUTPUT_DIR / "jobright_profile"


def _build_url(position: int, count: int, refresh: bool) -> str:
    return (f"{API_BASE}?refresh={'true' if refresh else 'false'}"
            f"&sortCondition=0&position={position}&count={count}&syncRerank=false")


def _posted_date(job: dict) -> str | None:
    """Best-effort 'YYYY-MM-DD' from publishTime (epoch s / ms) or an ISO string.
    VERIFY the unit against a live sample; handles both defensively."""
    v = job.get("publishTime")
    if isinstance(v, (int, float)) and v > 0:
        secs = v / 1000 if v > 1e12 else v  # ms vs s
        try:
            return datetime.fromtimestamp(secs, tz=timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, OSError, OverflowError):
            return None
    if isinstance(v, str) and v[:4].isdigit():
        return v[:10]
    return None


def _location(job: dict) -> str | None:
    loc = job.get("jobLocation")
    if not loc and isinstance(job.get("jobLocations"), list) and job["jobLocations"]:
        first = job["jobLocations"][0]
        loc = first.get("name") if isinstance(first, dict) else first
    if job.get("isRemote"):
        loc = f"{loc} (Remote)" if loc else "Remote"
    return loc


def _synth_description(item: dict, jr: dict, cr: dict) -> str:
    """The list endpoint carries no full JD, so synthesize a short context blob
    for the ATS scorer from the structured fields we do have. (Enrich later by
    fetching each job's detail endpoint for the real posting text.)"""
    bits = [
        jr.get("jobNlpTitle") or jr.get("jobTitle") or "",
        f"Company: {cr.get('companyName', '')}",
        f"Seniority: {jr.get('jobSeniority', '')}",
        f"Work model: {jr.get('workModel', '')}",
        f"Salary: {jr.get('salaryDesc', '')}",
        " ".join(cr.get("companyCategories") or []) if isinstance(cr.get("companyCategories"), list) else "",
        cr.get("companyDesc") or "",
    ]
    return "\n".join(b for b in bits if b).strip()


def parse_response(payload: dict) -> list[dict]:
    """Map the API envelope into raw jobs-table rows (pure; no network).

    Rows carry exactly the keys `jobsearch.score_and_route` / `save_jobs` expect;
    the scoring/legitimacy/routing pipeline fills in the rest.
    """
    if not payload or not payload.get("success"):
        return []
    rows: list[dict] = []
    for item in payload.get("result") or []:
        jr = item.get("jobResult") or {}
        cr = item.get("companyResult") or {}
        job_id = jr.get("jobId")
        if not job_id or not jr.get("jobTitle"):
            continue
        rows.append({
            "title": jr.get("jobTitle"),
            "company": cr.get("companyName"),
            "location": _location(jr),
            "url": JOB_URL_FMT.format(job_id=job_id),
            "date_posted": _posted_date(jr),
            "site": SITE,
            "description": _synth_description(item, jr, cr),
            # Carried for reference/debugging; not persisted (no column for it).
            "jobright_match": item.get("displayScore"),
        })
    return rows


def fetch_via_cookie(cookie: str, position: int = 0, count: int = 20,
                     refresh: bool = True) -> dict:
    """Hit the API directly with an exported session cookie. Returns the raw
    JSON envelope. Requires `requests` (already a project dep)."""
    try:
        import requests
    except ImportError:
        raise RuntimeError("`requests` not installed — needed for the cookie path.")
    headers = {
        "accept": "application/json",
        "cookie": cookie,
        "user-agent": "Mozilla/5.0",
        "referer": "https://jobright.ai/jobs/recommend",
    }
    resp = requests.get(_build_url(position, count, refresh), headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _logged_in(page) -> bool:
    """On the recommend page, a logged-out user is bounced to the landing page
    or shown a sign-in wall. Treat 'still on /jobs/recommend with no visible
    SIGN IN' as logged in."""
    if "/jobs/recommend" not in page.url:
        return False
    try:
        return page.get_by_text("SIGN IN", exact=False).count() == 0
    except Exception:
        return True


def login_playwright(timeout_s: int = 240) -> bool:  # pragma: no cover — interactive
    """One-time: open a headed browser, let the user log in, persist the session.

    Auto-detects a successful login by polling (no Enter needed), so it works
    however it's launched. Your credentials go straight into jobright in the
    window — this code never sees them; only the resulting session is saved to
    PROFILE_DIR, which later headless runs reuse."""
    import time

    from playwright.sync_api import sync_playwright

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    ok = False
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(str(PROFILE_DIR), headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(RECOMMEND_URL, wait_until="domcontentloaded", timeout=60000)
        print("\nA browser window opened. Log in to jobright and get to your Job "
              "Recommendations — I'll detect it automatically (waiting up to "
              f"{timeout_s // 60} min)…")
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if "/jobs/recommend" in page.url and _logged_in(page):
                time.sleep(2)  # let the session settle/persist
                ok = True
                break
            time.sleep(3)
        ctx.close()
    print("✅ Session saved — you're set. Run `--preview` / `--save` now." if ok else
          "⏱️ Didn't detect a login in time — re-run --login and reach the "
          "recommendations page.")
    return ok


def fetch_via_playwright(count: int = 40, headless: bool = True,
                         max_scrolls: int = 8) -> list[dict]:
    """Drive the persistent (logged-in) profile, scroll the recommend feed, and
    capture the /swan/recommend/list/jobs XHR responses the page fires — the
    same traffic a human browsing generates. Reuses `parse_response`."""
    from playwright.sync_api import sync_playwright

    if not PROFILE_DIR.exists():
        raise RuntimeError("No saved jobright session. Run "
                           "`python -m job_bot.jobright --login` once first.")
    captured: list[dict] = []
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(str(PROFILE_DIR), headless=headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        def _on_response(resp):
            if "recommend/list/jobs" in resp.url:
                try:
                    captured.append(resp.json())
                except Exception:
                    pass

        page.on("response", _on_response)
        page.goto(RECOMMEND_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2500)
        if not _logged_in(page):
            ctx.close()
            raise RuntimeError("jobright session expired — re-run "
                               "`python -m job_bot.jobright --login`.")
        # Scroll to page the feed until we have enough (or it stops growing).
        for _ in range(max_scrolls):
            rows_so_far = sum(len(parse_response(p)) for p in captured)
            if rows_so_far >= count:
                break
            page.mouse.wheel(0, 6000)
            page.wait_for_timeout(1800)
        ctx.close()

    seen: set[str] = set()
    rows: list[dict] = []
    for payload in captured:
        for r in parse_response(payload):
            if r["url"] not in seen:
                seen.add(r["url"])
                rows.append(r)
    return rows[:count]


def collect(pages: int = 5, per_page: int = 20, cookie: str | None = None) -> list[dict]:
    """Fetch up to `pages` pages via the cookie path, parse, and dedupe by URL.
    Stops early when a page returns empty (the feed is exhausted/stateful)."""
    cookie = cookie or os.getenv("JOBRIGHT_COOKIE")
    if not cookie:
        raise RuntimeError(
            "No JOBRIGHT_COOKIE set. Export your jobright session cookie into a "
            "gitignored .env as JOBRIGHT_COOKIE=... (or wire fetch_via_playwright)."
        )
    seen: set[str] = set()
    rows: list[dict] = []
    for i in range(pages):
        payload = fetch_via_cookie(cookie, position=i * per_page, count=per_page,
                                   refresh=(i == 0))
        page_rows = parse_response(payload)
        if not page_rows:
            break
        for r in page_rows:
            if r["url"] not in seen:
                seen.add(r["url"])
                rows.append(r)
    return rows


def parse_dom_rows(lines: list[str]) -> list[dict]:
    """Parse pipe-delimited cards scraped from the rendered recommend page
    (title|company|location|salary|type|workmodel|posted) into jobs rows.

    Best-effort FALLBACK for a one-time grab from a logged-in browser tab when
    neither the cookie nor Playwright path is set up. jobright's card classes are
    hashed (change on redeploys) and expose no jobId, so this is not durable and
    synthesizes a stable dedupe URL from company+title (not a deep link)."""
    import re
    import urllib.parse
    from datetime import date, timedelta

    rows: list[dict] = []
    for ln in lines:
        parts = [p.strip() for p in (ln.split("|") + [""] * 7)[:7]]
        title, company, location, salary, jtype, work, posted = parts
        if not title or not company:
            continue
        if work.lower() == "remote" and "remote" not in (location or "").lower():
            location = f"{location} (Remote)".strip(" ") if location else "Remote"
        dp = None
        m = re.search(r"(\d+)\s*(minute|hour|day|week)", posted, re.I)
        if m:
            n, unit = int(m.group(1)), m.group(2).lower()
            days = {"minute": 0, "hour": 0, "day": n, "week": n * 7}[unit]
            dp = (date.today() - timedelta(days=days)).isoformat()
        elif posted:
            dp = date.today().isoformat()
        slug = urllib.parse.quote_plus(f"{company}-{title}")[:120]
        desc = "\n".join(x for x in [title, f"Company: {company}",
                                     f"Type: {jtype}" if jtype else "",
                                     f"Work model: {work}" if work else "",
                                     f"Salary: {salary}" if salary else ""] if x)
        rows.append({
            "title": title, "company": company, "location": location or None,
            "url": f"https://jobright.ai/jobs/recommend?jr={slug}",
            "date_posted": dp, "site": SITE, "description": desc,
        })
    return rows


def import_dom_rows(lines: list[str], save: bool = True) -> dict:
    """Score/route DOM-scraped rows and (optionally) persist — one-time path."""
    from .ats_engine import load_profile
    from .jobsearch import save_jobs, score_and_route

    raw = parse_dom_rows(lines)
    if not raw:
        return {"fetched": 0, "saved": 0, "rows": []}
    scored = score_and_route(raw, load_profile(None))
    saved = save_jobs(scored) if save else 0
    return {"fetched": len(raw), "saved": saved, "rows": scored}


def run(method: str = "playwright", count: int = 40, pages: int = 5,
        save: bool = True, headless: bool = True) -> dict:
    """Collect jobright matches (via `playwright` [default] or `cookie`),
    score/route them, and optionally persist."""
    from .ats_engine import load_profile
    from .jobsearch import save_jobs, score_and_route

    if method == "cookie":
        raw = collect(pages=pages)
    else:
        raw = fetch_via_playwright(count=count, headless=headless)
    if not raw:
        return {"fetched": 0, "saved": 0, "rows": []}
    scored = score_and_route(raw, load_profile(None))
    saved = save_jobs(scored) if save else 0
    return {"fetched": len(raw), "saved": saved, "rows": scored}


def main() -> None:
    import argparse
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Import jobright.ai AI-matched jobs.")
    ap.add_argument("--login", action="store_true",
                    help="one-time: open a browser to log in and save the session (Playwright)")
    ap.add_argument("--preview", action="store_true", help="fetch + parse, print, don't save")
    ap.add_argument("--save", action="store_true", help="score/route and write to the jobs table")
    ap.add_argument("--method", choices=["playwright", "cookie"], default="playwright",
                    help="auth path (default: playwright)")
    ap.add_argument("--count", type=int, default=40, help="max jobs to pull (playwright)")
    ap.add_argument("--pages", type=int, default=5, help="max pages to fetch (cookie)")
    ap.add_argument("--show", action="store_true",
                    help="run the browser headed (visible) instead of headless")
    args = ap.parse_args()

    if args.login:
        login_playwright()
        return
    if not args.preview and not args.save:
        ap.print_help()
        return

    res = run(method=args.method, count=args.count, pages=args.pages,
              save=args.save, headless=not args.show)
    print(f"\njobright: fetched {res['fetched']}"
          + (f", saved {res['saved']} new" if args.save else " (preview, not saved)"))
    for r in res["rows"][:25]:
        match = r.get("jobright_match")
        print(f"  {r.get('priority', 0):>3.0f}pri  {r.get('ats_score', 0):>3.0f}ats  "
              f"{('m' + str(match)) if match else '':>4}  "
              f"{(r.get('title') or '')[:40]:40}  {(r.get('company') or '')[:24]}")


if __name__ == "__main__":
    main()
