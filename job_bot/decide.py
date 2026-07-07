"""Phase 3 CLI: decide whether to cold-apply or network first for a job.

Runs the full chain — parse JD (Phase 2), reverse-ATS score it, look up warm
contacts at the company, then issue a 🟢/🟡/🔴 verdict with concrete actions.

Usage:
    python -m job_bot.decide --file jd.txt
    python -m job_bot.decide --file jd.txt --url https://... --posted 2026-06-27
    python -m job_bot.decide --file jd.txt --company "Deloitte" --days 1
    python -m job_bot.decide --import-connections "Connections.csv"
    python -m job_bot.decide --list-connections
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

from . import config
from .ats_engine import load_profile, score
from .connections import import_linkedin_csv, matches_for_company
from .db import connect
from .decision_engine import decide
from .decision_models import DecisionReport
from .jd_parser import parse_jd


def _days_since(posted: str | None, days: int | None) -> int | None:
    if days is not None:
        return days
    if posted:
        try:
            d = datetime.strptime(posted, "%Y-%m-%d").date()
            return max(0, (date.today() - d).days)
        except ValueError:
            print(f"  ! couldn't parse --posted '{posted}' (use YYYY-MM-DD)")
    return None


def _read_jd(args) -> str:
    if args.file:
        return Path(args.file).read_text(encoding="utf-8", errors="replace")
    if args.text:
        return args.text
    if not sys.stdin.isatty():
        data = sys.stdin.read()
        if data.strip():
            return data
    raise SystemExit("Provide a JD via --file PATH, --text \"...\", or piped stdin.")


def print_report(r: DecisionReport) -> None:
    f = r.factors
    print("\n" + "=" * 64)
    print(f" NETWORK vs COLD-APPLY — {r.title or 'role'}"
          + (f" @ {r.company}" if r.company else ""))
    print("=" * 64)
    print(f" VERDICT: {r.verdict_label}")
    print(f" Confidence: {r.confidence*100:.0f}%")
    print("-" * 64)
    print(" Factors:")
    print(f"   Competition / volume   {f.competition*100:4.0f}%")
    print(f"   Resume strength (ATS)  {f.resume_strength*100:4.0f}%  (score {r.ats_score})")
    print(f"   Connection leverage    {f.connection_strength*100:4.0f}%"
          + ("  [recruiter contact!]" if f.recruiter_available else ""))
    if f.days_since_posting is not None:
        print(f"   Days since posting     {f.days_since_posting}")
    print(f"\n Why: {r.rationale}")

    if f.competition_notes:
        print("\n Competition read:")
        for n in f.competition_notes:
            print(f"   • {n}")

    if r.top_contacts:
        print("\n Warm contacts at this company:")
        for c in r.top_contacts:
            print(f"   • {c.name} — {c.title or '?'}  [{c.relationship}, warmth {c.warmth:.2f}]")
    else:
        print("\n Warm contacts at this company: none on file "
              "(import your LinkedIn export with --import-connections).")

    print("\n Recommended actions:")
    for i, a in enumerate(r.recommended_actions, 1):
        print(f"  {i}. {a}")
    print("=" * 64)


def _log_decision(r: DecisionReport) -> None:
    con = connect()
    con.execute(
        "INSERT INTO decisions (company, title, verdict, ats_score, competition, "
        "connection, report_json) VALUES (?,?,?,?,?,?,?)",
        (r.company, r.title, r.verdict, r.ats_score, r.factors.competition,
         r.factors.connection_strength, r.model_dump_json()),
    )
    con.commit()
    con.close()


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Network-vs-cold-apply decision (Phase 3).")
    ap.add_argument("--file", type=Path, help="JD text file")
    ap.add_argument("--text", help="JD text inline")
    ap.add_argument("--url", help="Job posting URL (for ATS detection)")
    ap.add_argument("--company", help="Override/ensure company name for connection lookup")
    ap.add_argument("--posted", help="Posting date YYYY-MM-DD")
    ap.add_argument("--days", type=int, help="Days since posting (alternative to --posted)")
    ap.add_argument("--profile", type=Path, help="Path to master_profile.json")
    ap.add_argument("--no-llm", action="store_true", help="Force heuristic JD parsing")
    ap.add_argument("--import-connections", type=Path, metavar="CSV",
                    help="Import a LinkedIn Connections.csv (or any roster) and exit")
    ap.add_argument("--relationship", default="first_degree",
                    help="Default relationship tag for an import (e.g. pse, umd, iefs, recruiter)")
    ap.add_argument("--list-connections", action="store_true",
                    help="List stored connections and exit")
    ap.add_argument("--referral-pack", action="store_true",
                    help="On a network-first verdict, auto-draft a referral request for "
                         "every warm contact at the company (logs them to outreach)")
    args = ap.parse_args()

    if args.import_connections:
        n = import_linkedin_csv(args.import_connections, default_relationship=args.relationship)
        print(f"Imported {n} connections from {args.import_connections.name} "
              f"(tagged '{args.relationship}').")
        return
    if args.list_connections:
        con = connect()
        rows = list(con.execute("SELECT name, company, title, relationship, warmth "
                                "FROM connections ORDER BY company, warmth DESC"))
        con.close()
        if not rows:
            print("No connections stored. Import with --import-connections Connections.csv")
            return
        print(f"{len(rows)} connection(s):")
        for r in rows:
            print(f"  {r['company']:<24} {r['name']:<22} {r['relationship']:<13} "
                  f"{r['warmth']:.2f}  {r['title'] or ''}")
        return

    jd_text = _read_jd(args)
    profile = load_profile(args.profile)
    job = parse_jd(jd_text, url=args.url, use_llm=False if args.no_llm else None)
    if args.company:
        job.company = args.company

    report_ats = score(job, profile)
    days = _days_since(args.posted, args.days)

    con = connect()
    matches = matches_for_company(con, job.company)
    con.close()

    decision = decide(job, report_ats.overall_score, matches, days_since_posting=days)
    _log_decision(decision)

    config.ensure_dirs()
    print_report(decision)
    print(f"\nLogged decision to {config.OUTPUT_DIR / 'job_bot.db'} (decisions table).")

    # Recommendation #7: on a network-first (🔴) verdict, auto-draft a referral
    # request for every warm contact so the user can act immediately.
    networky = decision.verdict in ("network_first", "red") or "network" in decision.verdict.lower()
    if decision.top_contacts and (args.referral_pack or networky):
        if not args.referral_pack:
            print("\n🔴 Network-first verdict — drafting a referral pack for every warm "
                  "contact (use the drafts below; re-run with --no-llm to force templates):")
        from .networking import build_plan
        pack = build_plan(job.company, job.title or "this role",
                          max_contacts=100, use_llm=False if args.no_llm else None)
        print("\n" + "=" * 64)
        print(f" REFERRAL PACK — {len(pack['contacts'])} draft(s) for {job.company}")
        print("=" * 64)
        for i, c in enumerate(pack["contacts"], 1):
            print(f"\n {i}. To {c['contact']} ({c['relationship']}, warmth {c['warmth']:.2f}) "
                  f"— {c['kind'].replace('_',' ')}, send {c['send_on']}:")
            for line in c["message"].splitlines():
                print(f"      {line}")
        print("\n" + "=" * 64)
        print("Drafts logged to the outreach table — `python -m job_bot.network --pending`.")


if __name__ == "__main__":
    main()
