"""Direct career-portal scanning — career-ops "portal scan", adapted.

JobSpy aggregators (LinkedIn/Indeed/Glassdoor) lag and dedupe imperfectly. The
freshest, most authoritative source is a company's own careers portal. Several
modern ATS platforms expose a clean, public JSON feed of open roles — no
scraping, no ToS grey area:

  * Greenhouse :  https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
  * Lever      :  https://api.lever.co/v0/postings/{token}?mode=json

This module pulls those feeds for a registry of the user's target employers,
filters to roles that match his search terms + market, and returns rows in the
exact shape jobsearch.save_jobs() expects — so portal roles flow into the same
pipeline, scoring, legitimacy check, and Action Center as scraped roles.

Big-4 / large-bank employers run Workday or Taleo, which have no clean public
feed; for those, portal_hint() returns the direct portal URL + strategy instead,
so the tool still tells John exactly where to look.

The registry lives in code (DEFAULT_PORTALS) and can be extended without a code
change via a user-editable JSON file at data/portals.json — add a company's
board token there as you discover it and the next scan picks it up.
"""

from __future__ import annotations

import json

from . import config

# --- Target-employer registry -------------------------------------------------
# ats: "greenhouse" | "lever" -> scanned live via public JSON API.
#      "workday" | "taleo" | "manual" -> no public feed; portal_hint() only.
# token: the board slug in the ATS URL. VERIFY before trusting counts — a wrong
# token simply 404s and is skipped, never crashes.
DEFAULT_PORTALS: list[dict] = [
    # Firms John actually applied to that run Workday/Taleo (manual portal guidance):
    {"company": "Deloitte", "ats": "workday",
     "url": "https://apply.deloitte.com/careers/SearchJobs"},
    {"company": "KPMG", "ats": "workday",
     "url": "https://www.kpmguscareers.com/jobs/"},
    {"company": "EY", "ats": "workday",
     "url": "https://careers.ey.com/ey/search/"},
    {"company": "PwC", "ats": "taleo",
     "url": "https://jobs.us.pwc.com/"},
    {"company": "Grant Thornton", "ats": "workday",
     "url": "https://www.grantthornton.com/careers"},
    {"company": "Protiviti", "ats": "workday",
     "url": "https://jobs.protiviti.com/"},
    {"company": "Capital One", "ats": "workday",
     "url": "https://www.capitalonecareers.com/search-jobs"},
    # Greenhouse/Lever examples (live-scannable). Extend via data/portals.json.
    # Tokens here are illustrative — verify against the company's real board URL.
    {"company": "Robinhood", "ats": "greenhouse", "token": "robinhood"},
    {"company": "Stripe", "ats": "greenhouse", "token": "stripe"},
]

# Roles John cares about — a portal role is kept only if its title matches one.
DEFAULT_KEYWORDS = [
    "audit", "risk", "control", "compliance", "assurance", "analyst",
    "accounting", "finance", "cyber", "security", "data",
]


def _requests():
    try:
        import requests
        return requests
    except Exception:
        return None


def load_registry() -> list[dict]:
    """DEFAULT_PORTALS overlaid with the user's data/portals.json, if present."""
    portals = list(DEFAULT_PORTALS)
    override = config.OUTPUT_DIR / "portals.json"
    try:
        if override.exists():
            extra = json.loads(override.read_text(encoding="utf-8"))
            if isinstance(extra, list):
                portals += [p for p in extra if isinstance(p, dict) and p.get("company")]
    except Exception:
        pass
    return portals


def _match(title: str, keywords: list[str]) -> bool:
    low = (title or "").lower()
    return any(k in low for k in keywords)


import re as _re

# Senior-title markers — a portal role is dropped if its title matches any. Word-
# boundary anchored so "Lead"/"Head"/"Staff" match at the end of a title too, and
# roman-numeral levels (III/IV/V) are caught. John is entry-level (new grad).
_SENIOR_RE = _re.compile(
    r"\b(senior|sr\.?|staff|principal|lead|manager|mgr|director|"
    r"vp|vice president|head|chief|officer|counsel|architect|partner|"
    r"expert|distinguished|ii|iii|iv)\b", _re.I)


def _entry_level(title: str) -> bool:
    """Keep entry/junior titles, drop obvious senior/lead/exec roles."""
    return not _SENIOR_RE.search(title or "")


def _fetch_greenhouse(token: str, keywords: list[str]) -> list[dict]:
    req = _requests()
    if not req:
        return []
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
    try:
        r = req.get(url, timeout=15)
        if r.status_code != 200:
            return []
        data = r.json()
    except Exception:
        return []
    rows = []
    for j in data.get("jobs", []):
        title = j.get("title", "")
        if not _match(title, keywords) or not _entry_level(title):
            continue
        loc = (j.get("location") or {}).get("name", "")
        rows.append({
            "title": title, "location": loc, "url": j.get("absolute_url", ""),
            "site": "greenhouse", "date_posted": (j.get("updated_at") or "")[:10],
            "description": _strip_html(j.get("content", "")),
        })
    return rows


def _fetch_lever(token: str, keywords: list[str]) -> list[dict]:
    req = _requests()
    if not req:
        return []
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    try:
        r = req.get(url, timeout=15)
        if r.status_code != 200:
            return []
        data = r.json()
    except Exception:
        return []
    rows = []
    for j in data if isinstance(data, list) else []:
        title = j.get("text", "")
        if not _match(title, keywords) or not _entry_level(title):
            continue
        cats = j.get("categories", {}) or {}
        rows.append({
            "title": title, "location": cats.get("location", ""),
            "url": j.get("hostedUrl", ""), "site": "lever",
            "date_posted": "", "description": _strip_html(j.get("descriptionPlain")
                                                          or j.get("description", "")),
        })
    return rows


def _strip_html(s: str) -> str:
    import re
    return re.sub(r"<[^>]+>", " ", s or "").replace("&nbsp;", " ").strip()[:8000]


def portal_hint(entry: dict) -> str:
    """Human guidance for portals with no public feed (Workday/Taleo/manual)."""
    ats = entry.get("ats", "manual")
    url = entry.get("url", "")
    tip = {
        "workday": "Workday portal — search your role, filter to Entry/Associate, "
                   "and use the exact JD title in your resume header (Workday keys off it).",
        "taleo": "Taleo portal — older parser; match keywords literally and apply "
                 "with a plain single-column resume.",
        "manual": "Check this portal directly for fresh openings.",
    }.get(ats, "Check this portal directly.")
    return f"{entry['company']}: {url}\n    → {tip}"


def scan(keywords: list[str] | None = None, *, companies: list[str] | None = None) -> dict:
    """Pull live openings from every Greenhouse/Lever board in the registry.

    Returns {"rows": [...save_jobs-shaped...], "scanned": [...], "manual": [...]}.
    `rows` is empty (gracefully) if `requests` or the network is unavailable.
    """
    keywords = keywords or DEFAULT_KEYWORDS
    registry = load_registry()
    if companies:
        want = {c.lower() for c in companies}
        registry = [e for e in registry if e.get("company", "").lower() in want]

    rows: list[dict] = []
    scanned: list[dict] = []
    manual: list[dict] = []
    for e in registry:
        ats = e.get("ats")
        if ats == "greenhouse" and e.get("token"):
            got = _fetch_greenhouse(e["token"], keywords)
        elif ats == "lever" and e.get("token"):
            got = _fetch_lever(e["token"], keywords)
        else:
            manual.append(e)
            continue
        for row in got:
            row["company"] = e["company"]
        rows.extend(got)
        scanned.append({"company": e["company"], "ats": ats, "found": len(got)})
    return {"rows": rows, "scanned": scanned, "manual": manual}


def scan_and_save(keywords: list[str] | None = None, profile: dict | None = None) -> dict:
    """Scan portals, score/route/legitimacy-check like jobsearch, and persist."""
    from .ats_engine import load_profile
    from .deprecated.jobsearch import save_jobs, score_and_route

    result = scan(keywords)
    rows = result["rows"]
    if not rows:
        return {"scanned": result["scanned"], "manual": result["manual"],
                "saved": 0, "top": []}
    profile = profile or load_profile(None)
    scored = score_and_route(rows, profile)
    saved = save_jobs(scored)
    top = sorted(scored, key=lambda x: x.get("priority", 0), reverse=True)[:10]
    return {"scanned": result["scanned"], "manual": result["manual"],
            "saved": saved, "top": top}


def main() -> None:
    import argparse
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Direct career-portal scan (career-ops portal scan).")
    ap.add_argument("--save", action="store_true", help="Score, route, and save into the pipeline")
    ap.add_argument("--company", action="append", help="Limit to these companies (repeatable)")
    ap.add_argument("--keywords", help="Comma-separated title keywords to keep")
    args = ap.parse_args()

    kws = [k.strip() for k in args.keywords.split(",")] if args.keywords else None
    if args.save:
        res = scan_and_save(kws)
    else:
        res = scan(kws, companies=args.company)
        res.setdefault("saved", 0)

    print("\nPortal scan:")
    for s in res.get("scanned", []):
        print(f"  · {s['company']:<20} [{s['ats']}]  {s['found']} matching roles")
    if not res.get("scanned"):
        print("  (no live-feed portals returned rows — `requests` or network may be unavailable)")
    if res.get("saved"):
        print(f"\nSaved {res['saved']} new roles into the pipeline.")
    if res.get("top"):
        print("\nTop portal roles by priority:")
        for r in res["top"]:
            print(f"  {r.get('priority',0):>4.0f}  {(r.get('company') or '?')[:18]:<18} "
                  f"{(r.get('title') or '')[:44]}")

    manual = res.get("manual", [])
    if manual:
        print("\nPortals with no public feed — check these directly:")
        for e in manual:
            print("  " + portal_hint(e))


if __name__ == "__main__":
    main()
