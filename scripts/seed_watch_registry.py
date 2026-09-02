#!/usr/bin/env python3
"""Point the company tracker at the verified job-board endpoints in watch_registry.

The tracker holds 200+ target companies, but `career_site_url` was populated on 0
of them and `ats_platform` on exactly 1 - so the posting watcher had nothing to
poll. The bottleneck was never code, it was this data: ATS tokens are not reliably
guessable from a company name, and token-guessing produces confident garbage
(`costar` is the astrology app, `diligent` is a construction firm, SmartRecruiters
returns HTTP 200 for tokens that do not exist).

job_bot/watch_registry.py holds the curated result of probing every tracked
company against four public APIs. This script writes those coordinates onto the
matching `companies` rows and flags them watch_enabled.

Idempotent: re-running only rewrites the same values. Companies absent from the
registry are left untouched with watch_enabled unset - they keep the manual
next_check_due nudge, which is the right treatment for the small firms whose
careers pages have no feed at all.

Usage:  python scripts/seed_watch_registry.py [--apply]
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from job_bot import companies, watch_registry  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    args = ap.parse_args()

    entries = watch_registry.all_entries()
    tracked = {c["name"]: c for c in companies.list_all()}

    matched, missing = [], []
    for e in entries:
        row = tracked.get(e["name"])
        (matched if row else missing).append((e, row))

    print(f"registry entries : {len(entries)}")
    print(f"matched in tracker: {len(matched)}")
    print(f"not in tracker    : {len(missing)}")
    for e, _ in missing:
        print(f"    ? {e['name']} ({e['platform']})")

    by_platform = Counter(e["platform"] for e, _ in matched)
    for plat, n in by_platform.most_common():
        print(f"    {plat:<16} {n}")

    if not args.apply:
        print("\nDry run - nothing written. Re-run with --apply to commit.")
        return 0

    written = 0
    for e, row in matched:
        fields = {
            "ats_platform": e["platform"],
            "watch_enabled": 1,
            "last_watch_error": None,
        }
        if e["platform"] == "Workday":
            fields.update(ats_host=e["host"], ats_tenant=e["tenant"], ats_site=e["site"],
                          career_site_url=f"https://{e['host']}/en-US/{e['site']}")
            fields["ats_token"] = None
        else:
            fields["ats_token"] = e["token"]
            fields["career_site_url"] = {
                "Greenhouse": f"https://boards.greenhouse.io/{e['token']}",
                "Ashby": f"https://jobs.ashbyhq.com/{e['token']}",
                "SmartRecruiters": f"https://jobs.smartrecruiters.com/{e['token']}",
            }.get(e["platform"])
        companies.update(row["id"], **fields)
        written += 1

    print(f"\nAPPLIED. {written} companies are now watched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
