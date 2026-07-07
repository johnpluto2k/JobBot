"""Tracking & communications CLI (recommendations layer).

    # Triage emails (paste a few, or pipe JSON; or wire the Gmail MCP)
    python -m job_bot.pipeline --inbox-demo
    python -m job_bot.pipeline --classify-subject "Interview invite - Deloitte" --from "ta@deloitte.com"

    # Schedule prep around an interview (and print calendar events)
    python -m job_bot.pipeline --prep-plan --company Deloitte --role "Technology Risk" \
        --firm big4 --date 2026-07-15 --ics

    # Draft a post-interview thank-you
    python -m job_bot.pipeline --thankyou --company Deloitte --role "Technology Risk" \
        --interviewer "Marcus Webb" --topics "ITGC testing, the team's AI-risk work"

    # The unified action queue across the whole system
    python -m job_bot.pipeline --queue
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from . import config
from .ats_engine import load_profile
from .db import connect


def _utf8():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


DEMO_EMAILS = [
    {"received_at": "2026-06-28", "sender": "talent@deloitte.com",
     "subject": "Next steps: Technology Risk interview invitation",
     "body": "We'd love to schedule a first-round interview. Please share your availability."},
    {"received_at": "2026-06-27", "sender": "no-reply@greenhouse.io",
     "subject": "Your Stripe application — HireVue assessment",
     "body": "Please complete the online assessment within 5 days."},
    {"received_at": "2026-06-26", "sender": "recruiting@kpmg.com",
     "subject": "Update on your application",
     "body": "Unfortunately, we have decided to move forward with other candidates."},
    {"received_at": "2026-06-25", "sender": "ta@capitalone.com",
     "subject": "Thanks for applying — reaching out",
     "body": "A recruiter received your application and wanted to connect about timeline."},
]


def _print_triage(rows):
    icon = {"offer": "🎉", "interview_invite": "📅", "assessment": "📝",
            "recruiter_reply": "💬", "rejection": "❌", "other": "•"}
    print(f"\n{'CATEGORY':<18} {'COMPANY':<14} SUBJECT")
    print("-" * 78)
    for r in rows:
        print(f"{icon.get(r['category'],'•')} {r['category']:<16} {(r['company'] or '—')[:14]:<14} "
              f"{r['subject'][:40]}")
        print(f"   → {r['action']}")


def cmd_queue() -> None:
    today = date.today().isoformat()
    con = connect()
    print("\n=== ACTION QUEUE — what needs attention ===")

    inv = list(con.execute("SELECT followup_date, contact_name, company, kind FROM outreach "
                           "WHERE status='drafted' AND followup_date<=? ORDER BY followup_date", (today,)))
    print(f"\n📨 Outreach follow-ups due ({len(inv)}):")
    for r in inv:
        print(f"   {r['followup_date']}  {r['contact_name']} @ {r['company']} ({r['kind']})")

    up = list(con.execute("SELECT scheduled_at, company, role_title, round_name, status "
                          "FROM interviews WHERE status IN ('scheduled','prepped') ORDER BY scheduled_at"))
    print(f"\n📅 Upcoming interviews ({len(up)}):")
    for r in up:
        print(f"   {r['scheduled_at']}  {r['round_name']} — {r['role_title']} @ {r['company']}")

    em = list(con.execute("SELECT received_at, company, category, action FROM tracked_emails "
                          "WHERE handled=0 AND category IN "
                          "('interview_invite','assessment','offer') ORDER BY received_at DESC"))
    print(f"\n⚡ Unhandled email actions ({len(em)}):")
    for r in em:
        print(f"   [{r['category']}] {r['company'] or '—'} — {r['action']}")

    off = list(con.execute("SELECT company, role_title, deadline, base FROM offers "
                           "WHERE status='open' ORDER BY deadline"))
    print(f"\n💰 Open offers to decide ({len(off)}):")
    for r in off:
        dl = f" — decide by {r['deadline']}" if r["deadline"] else ""
        print(f"   {(r['company'] or '—')[:18]:<18} base ${r['base'] or 0:,.0f}{dl}")

    hot = list(con.execute("SELECT priority, company, title, status FROM jobs "
                           "WHERE status='new' ORDER BY priority DESC LIMIT 5"))
    print(f"\n🔥 Top new postings to act on ({len(hot)}):")
    for r in hot:
        print(f"   {r['priority']:>4.0f}  {(r['company'] or '—')[:18]:<18} {(r['title'] or '')[:36]}")
    con.close()
    print("\n" + "=" * 50)


def main() -> None:
    _utf8()
    ap = argparse.ArgumentParser(description="Tracking & communications (recommendations layer).")
    ap.add_argument("--inbox-demo", action="store_true", help="Triage a built-in sample inbox")
    ap.add_argument("--inbox-json", type=Path, help="Triage emails from a JSON file (list of {sender,subject,body,received_at})")
    ap.add_argument("--classify-subject", help="Classify a single email subject")
    ap.add_argument("--from", dest="sender", default="", help="Sender for --classify-subject")
    ap.add_argument("--body", default="", help="Body for --classify-subject")

    ap.add_argument("--prep-plan", action="store_true")
    ap.add_argument("--thankyou", action="store_true")
    ap.add_argument("--brief", action="store_true", help="Company research brief")
    ap.add_argument("--news", action="append", default=[],
                    help="A recent news headline (repeatable) to weave into the brief")
    ap.add_argument("--queue", action="store_true")
    ap.add_argument("--rejections", action="store_true", help="Rejection-pattern analysis")
    ap.add_argument("--log-rejection", action="store_true", help="Log a rejection")
    ap.add_argument("--stage", help="Rejection stage: ats_screen/assessment/recruiter_screen/"
                                    "first_round/superday/final")

    ap.add_argument("--company")
    ap.add_argument("--role", default="this role")
    ap.add_argument("--firm")
    ap.add_argument("--date", help="Interview date YYYY-MM-DD[THH:MM]")
    ap.add_argument("--interviewer")
    ap.add_argument("--topics", help="Comma-separated discussion points")
    ap.add_argument("--ics", action="store_true", help="Also write prep events to data/prep_plan.ics")
    ap.add_argument("--profile", type=Path)
    ap.add_argument("--no-llm", action="store_true")
    args = ap.parse_args()
    use_llm = False if args.no_llm else None

    if args.inbox_demo or args.inbox_json:
        from .inbox import triage
        emails = DEMO_EMAILS if args.inbox_demo else json.loads(args.inbox_json.read_text("utf-8"))
        _print_triage(triage(emails))
        print(f"\nLogged {len(emails)} emails to tracked_emails; matched job statuses updated.")
        return

    if args.classify_subject:
        from .inbox import classify_email
        r = classify_email(args.classify_subject, args.body, args.sender)
        print(f"category : {r['category']}\ncompany  : {r['company']}\naction   : {r['action']}")
        return

    if args.prep_plan:
        if not (args.company and args.date):
            raise SystemExit("--prep-plan needs --company and --date.")
        from .prep_plan import build_prep_plan, calendar_events, schedule_interview
        plan = build_prep_plan(args.company, args.role, args.firm, args.date)
        schedule_interview(args.company, args.role, args.firm, args.date)
        print(f"\n=== PREP PLAN — {args.role} @ {args.company} "
              f"({plan['days_until']} days out) ===")
        if plan["firm_note"]:
            print(f"Firm: {plan['firm_note']}")
        for b in plan["blocks"]:
            print(f"\n  {b['date']}  {b['start_hour']:02d}:00  {b['title']}")
            print(f"     {b['focus']}")
        events = calendar_events(plan)
        out = config.OUTPUT_DIR / "prep_plan_events.json"
        config.ensure_dirs()
        out.write_text(json.dumps(events, indent=2), encoding="utf-8")
        print(f"\nCalendar events ({len(events)}) -> {out}")
        if args.ics:
            ics = _to_ics(events)
            (config.OUTPUT_DIR / "prep_plan.ics").write_text(ics, encoding="utf-8")
            print(f"ICS -> {config.OUTPUT_DIR / 'prep_plan.ics'}  (import into any calendar)")
        return

    if args.thankyou:
        if not args.company:
            raise SystemExit("--thankyou needs --company (and ideally --interviewer/--topics).")
        from .thankyou import generate_thankyou
        profile = load_profile(args.profile)
        topics = [t.strip() for t in (args.topics or "").split(",") if t.strip()]
        text = generate_thankyou(profile, args.company, args.role, args.interviewer, topics,
                                 use_llm=use_llm)
        print("\n" + text)
        slug = (args.company or "company").lower().replace(" ", "_")
        out = config.OUTPUT_DIR / f"thankyou_{slug}.txt"
        config.ensure_dirs()
        out.write_text(text, encoding="utf-8")
        print(f"\nSaved {out}")
        return

    if args.log_rejection:
        if not args.company:
            raise SystemExit("--log-rejection needs --company (and ideally --stage / --role).")
        from .rejections import log_rejection
        rid = log_rejection(args.company, role_title=(args.role if args.role != "this role" else None),
                            stage=args.stage)
        print(f"Logged rejection #{rid} for {args.company}"
              + (f" ({args.stage})" if args.stage else "") + ".")
        return

    if args.brief:
        if not args.company:
            raise SystemExit("--brief needs --company (and ideally --role / --news).")
        from .company_research import build_brief, format_brief
        brief = build_brief(args.company, args.role, news=args.news or None, use_llm=use_llm)
        print(format_brief(brief))
        slug = args.company.lower().replace(" ", "_").replace("&", "and")
        out = config.OUTPUT_DIR / f"brief_{slug}.json"
        config.ensure_dirs()
        out.write_text(json.dumps(brief, indent=2), encoding="utf-8")
        print(f"Saved {out}")
        return

    if args.rejections:
        from .rejections import analyze
        _print_rejections(analyze())
        return

    if args.queue:
        cmd_queue()
        return

    ap.print_help()


def _print_rejections(a: dict) -> None:
    if a.get("total", 0) == 0:
        print("\nNo rejections logged yet. They auto-log from inbox triage, or add one with "
              "`--log-rejection --company X --stage first_round`.")
        return
    print(f"\n=== REJECTION ANALYSIS ({a['total']} logged) ===")
    print(f"\n By stage:     " + ", ".join(f"{k}={v}" for k, v in a["by_stage"].items()))
    print(f" By role type: " + ", ".join(f"{k}={v}" for k, v in a["by_role_type"].items()))
    print(f" By ATS band:  " + ", ".join(f"{k}={v}" for k, v in a["by_ats_band"].items()))
    print(f" By tier:      " + ", ".join(f"{k}={v}" for k, v in a["by_tier"].items()))
    if a.get("avg_ats_score") is not None:
        print(f" Avg ATS on rejected apps: {a['avg_ats_score']}")
    print("\n Insights:")
    for i in a["insights"]:
        print(f"   • {i}")
    if a["recommendations"]:
        print("\n Recommendations:")
        for r in a["recommendations"]:
            print(f"   → {r}")
    print("=" * 50)


def _to_ics(events: list[dict]) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Job Bot//Prep//EN"]
    for i, e in enumerate(events):
        s = e["start"]["dateTime"].replace("-", "").replace(":", "")
        en = e["end"]["dateTime"].replace("-", "").replace(":", "")
        lines += ["BEGIN:VEVENT", f"UID:jobbot-{i}@local",
                  f"DTSTART:{s}", f"DTEND:{en}",
                  f"SUMMARY:{e['summary']}",
                  f"DESCRIPTION:{e['description'].replace(chr(10), ' ')}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
