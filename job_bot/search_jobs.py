"""Phase 5 CLI: search job boards, route by market tier, score, and rank.

Usage:
    python -m job_bot.search_jobs --term "IT audit" --location "Washington, DC" --results 15
    python -m job_bot.search_jobs --term "data analyst" --remote --sites indeed,linkedin
    python -m job_bot.search_jobs --list            # show stored jobs ranked by priority
"""

from __future__ import annotations

import argparse
import sys

from .ats_engine import load_profile
from .db import connect
from .jobsearch import save_jobs, score_and_route, search


def _print_rows(rows: list[dict]) -> None:
    print(f"\n{'PRI':>4}  {'TIER':<18} {'ATS':>4}  {'SITE':<10} {'COMPANY':<22} TITLE")
    print("-" * 100)
    for r in rows[:40]:
        print(f"{r.get('priority',0):>4.0f}  {(r.get('market_tier') or '')[:18]:<18} "
              f"{r.get('ats_score',0):>4.0f}  {(r.get('site') or '')[:10]:<10} "
              f"{(r.get('company') or '')[:22]:<22} {(r.get('title') or '')[:36]}")


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Search + route + rank jobs (Phase 5).")
    ap.add_argument("--term", help="Search term, e.g. 'IT audit'")
    ap.add_argument("--location", default="", help="City, ST or 'Remote'")
    ap.add_argument("--sites", default="indeed",
                    help="Comma list: indeed,linkedin,glassdoor,google,zip_recruiter "
                         "(default: indeed — the reliable source; LinkedIn is opt-in)")
    ap.add_argument("--linkedin", action="store_true",
                    help="Also scrape LinkedIn (bonus source; throttles at ~10 pages/IP)")
    ap.add_argument("--results", type=int, default=15)
    ap.add_argument("--hours-old", type=int, default=None, help="Only postings newer than N hours")
    ap.add_argument("--remote", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="Re-scrape even if the same search ran within the last hour")
    ap.add_argument("--no-score", action="store_true", help="Skip per-job ATS scoring (faster)")
    ap.add_argument("--profile", help="Path to master_profile.json")
    ap.add_argument("--list", action="store_true", help="List stored jobs and exit")
    args = ap.parse_args()

    if args.list:
        con = connect()
        rows = [dict(r) for r in con.execute(
            "SELECT title, company, location, site, market_tier, ats_score, priority, status "
            "FROM jobs ORDER BY priority DESC LIMIT 40")]
        con.close()
        if not rows:
            print("No jobs stored yet. Run a search first.")
            return
        _print_rows(rows)
        return

    if not args.term:
        raise SystemExit("Provide --term to search (or --list to show stored jobs).")

    profile = load_profile(args.profile)
    sites = [s.strip() for s in args.sites.split(",") if s.strip()]
    if args.linkedin and "linkedin" not in sites:
        sites.append("linkedin")
    print(f"Searching {sites} for '{args.term}' in '{args.location or 'United States'}' ...")
    rows = search(args.term, args.location, sites=sites, results=args.results,
                  hours_old=args.hours_old, is_remote=args.remote, force=args.force)
    if not rows:
        print("\nNo postings returned (JobSpy unavailable, blocked, or zero matches).")
        print("Routing/scoring still works on manual postings via "
              "`python -m job_bot.score_job` and `python -m job_bot.generate`.")
        return

    print(f"Got {len(rows)} postings — scoring + routing ...")
    routed = score_and_route(rows, profile, score_each=not args.no_score)
    saved = save_jobs(routed)
    _print_rows(routed)
    print(f"\nSaved {saved} new postings to the jobs table (data/job_bot.db).")
    print("Tip: feed a top posting into `python -m job_bot.generate --text \"...\"` to tailor.")


if __name__ == "__main__":
    main()
