"""Phase 6 CLI: networking plan + outreach drafts for a company/role.

Usage:
    python -m job_bot.network --company Deloitte --role "Technology Risk Analyst"
    python -m job_bot.network --file jd.txt            # infer company + role from a JD
    python -m job_bot.network --pending                # show scheduled follow-ups
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .db import connect
from .networking import build_plan


def _infer_from_jd(path: Path | None, text: str | None) -> tuple[str | None, str | None]:
    from .jd_parser import parse_jd
    raw = path.read_text(encoding="utf-8", errors="replace") if path else (text or "")
    if not raw.strip():
        return None, None
    job = parse_jd(raw, use_llm=False)
    return job.company, job.title


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Networking plan + outreach drafts (Phase 6).")
    ap.add_argument("--company")
    ap.add_argument("--role", default="this role")
    ap.add_argument("--file", type=Path, help="Infer company/role from a JD file")
    ap.add_argument("--text", help="Infer company/role from inline JD text")
    ap.add_argument("--candidate", default="John")
    ap.add_argument("--max", type=int, default=3, help="Max contacts to draft for")
    ap.add_argument("--all", action="store_true",
                    help="Draft a referral request for EVERY warm contact (referral pack)")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--pending", action="store_true", help="Show scheduled outreach/follow-ups")
    args = ap.parse_args()

    if args.pending:
        con = connect()
        rows = [dict(r) for r in con.execute(
            "SELECT contact_name, company, role_title, kind, status, sent_date, followup_date "
            "FROM outreach ORDER BY followup_date")]
        con.close()
        if not rows:
            print("No outreach scheduled yet.")
            return
        today = date.today().isoformat()
        print(f"{'DUE':<12} {'STATUS':<9} {'CONTACT':<20} {'COMPANY':<16} KIND")
        print("-" * 74)
        for r in rows:
            due = r.get("followup_date") or r.get("sent_date") or ""
            flag = " ⏰" if due and due <= today and r["status"] != "replied" else ""
            print(f"{due:<12} {r['status']:<9} {(r['contact_name'] or '')[:20]:<20} "
                  f"{(r['company'] or '')[:16]:<16} {r['kind']}{flag}")
        return

    company, role = args.company, args.role
    if args.file or args.text:
        inferred_c, inferred_r = _infer_from_jd(args.file, args.text)
        company = company or inferred_c
        if role == "this role" and inferred_r:
            role = inferred_r
    if not company:
        raise SystemExit("Provide --company (or a JD via --file/--text to infer it).")

    max_contacts = 100 if args.all else args.max
    plan = build_plan(company, role, candidate=args.candidate, max_contacts=max_contacts,
                      use_llm=False if args.no_llm else None)

    print("\n" + "=" * 64)
    print(f" NETWORKING PLAN — {role} @ {company}")
    print("=" * 64)
    print(f" Connection leverage: {plan['connection_strength']*100:.0f}%"
          + ("  [recruiter on file]" if plan["recruiter_available"] else ""))
    if not plan["contacts"]:
        print("\n No warm contacts on file for this company.")
        print(" Import your LinkedIn export: "
              "python -m job_bot.decide --import-connections Connections.csv")
        print(" Then search LinkedIn for UMD / Pi Sigma Epsilon alums there.")
        return
    print(f" Cadence: send day 0, follow up at +{plan['cadence_days'][1]} and "
          f"+{plan['cadence_days'][2]} days.\n")

    for i, c in enumerate(plan["contacts"], 1):
        print("-" * 64)
        print(f" {i}. {c['contact']} — {c['title'] or '?'}  "
              f"[{c['relationship']}, warmth {c['warmth']:.2f}]")
        print(f"    Draft ({c['kind'].replace('_',' ')}), send {c['send_on']}, "
              f"follow up {', '.join(c['followup_dates'])}:")
        for line in c["message"].splitlines():
            print(f"      {line}")
        print()
    print("=" * 64)
    print("Drafts logged to the outreach table — see `--pending` for the follow-up queue.")


if __name__ == "__main__":
    main()
