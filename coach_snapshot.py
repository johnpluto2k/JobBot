#!/usr/bin/env python3
"""Read-only pipeline snapshot for the career-coach skill.

Usage: python3 pipeline_snapshot.py /path/to/"Job Bot"

Prints a compact JSON object with the canonical application funnel, upcoming
interviews, due follow-ups, unhandled recruiter email, fresh high-priority
postings, and (best-effort) the growth plan. Never writes to the database or
any file — every query here is a read.
"""
import json
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({"error": 'usage: pipeline_snapshot.py "<path to Job Bot folder>"'}))
        return
    repo = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(repo))

    out = {}

    # 1. Canonical funnel — stdlib-only (sqlite3 + optional python-dotenv), always works.
    try:
        from job_bot.applications import summary
        out["funnel"] = summary()
    except Exception as exc:
        out["funnel_error"] = str(exc)

    # 2. Time-sensitive items — straight SQL, no extra dependencies.
    try:
        from job_bot.db import connect
        con = connect()
        out["upcoming_interviews"] = [dict(r) for r in con.execute(
            "SELECT company, role_title, round_name, scheduled_at, status FROM interviews "
            "WHERE status IN ('scheduled','prepped') ORDER BY scheduled_at LIMIT 10")]
        out["followups_due"] = [dict(r) for r in con.execute(
            "SELECT contact_name, company, kind, followup_date FROM outreach "
            "WHERE status='drafted' AND followup_date<=date('now') ORDER BY followup_date LIMIT 10")]
        out["unhandled_recruiter_email"] = [dict(r) for r in con.execute(
            "SELECT received_at, company, category FROM tracked_emails WHERE handled=0 "
            "AND category IN ('interview_invite','assessment','offer','recruiter_reply') "
            "ORDER BY received_at DESC LIMIT 10")]
        out["fresh_high_priority_jobs"] = [dict(r) for r in con.execute(
            "SELECT title, company, priority FROM jobs WHERE status='new' "
            "ORDER BY priority DESC LIMIT 5")]
        con.close()
    except Exception as exc:
        out["db_error"] = str(exc)

    # 3. Growth plan — needs pydantic-backed job_bot.jd_models; best-effort only.
    try:
        from job_bot.growth import build_plan
        plan = build_plan()
        out["growth_insights"] = plan.get("insights", [])
        out["growth_focus_fields"] = [f["field"] for f in plan.get("per_field", [])]
    except Exception as exc:
        out["growth_error"] = (
            f"{exc} (if this is a missing-package error, run: "
            f"pip install pydantic --break-system-packages, then retry)"
        )

    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
