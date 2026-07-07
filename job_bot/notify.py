"""Notification System (Recommendation #11).

Surfaces time-sensitive alerts the moment they matter — primarily fresh,
high-priority job postings (applying early to a competitive role is a real
edge), plus offer deadlines and overdue follow-ups. Each alert is deduped via
the `notifications` table so you never get pinged twice for the same thing.

Sinks, in order of availability:
  • console  — always (prints the alert)
  • webhook  — if `--webhook URL` or env `JOB_BOT_WEBHOOK` is set; posts a
    Slack-compatible JSON payload ({"text": ...}) via urllib (stdlib, no deps).

Designed to be run on a schedule (Task Scheduler / cron / a Claude cron task):
each run only emits *new* alerts.
"""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import date, datetime, timedelta

from .db import connect


def _already_sent(con, kind: str, ref: str) -> bool:
    row = con.execute("SELECT 1 FROM notifications WHERE kind=? AND ref=? LIMIT 1",
                      (kind, ref)).fetchone()
    return row is not None


def _record(con, kind: str, ref: str, company: str | None, title: str | None,
            channel: str, payload: str) -> None:
    con.execute("INSERT INTO notifications (kind, ref, company, title, channel, payload) "
                "VALUES (?,?,?,?,?,?)", (kind, ref, company, title, channel, payload))


def _fresh_jobs(con, max_age_hours: int, min_priority: float, tiers: list[int] | None):
    """High-priority, recently-posted jobs not yet alerted."""
    cutoff = (datetime.now() - timedelta(hours=max_age_hours)).date().isoformat()
    rows = con.execute(
        "SELECT url, company, title, location, priority, market_tier, tier_num, "
        "ats_score, date_posted, status FROM jobs "
        "WHERE priority >= ? ORDER BY priority DESC", (min_priority,)).fetchall()
    out = []
    for r in rows:
        if tiers and r["tier_num"] not in tiers:
            continue
        # treat unknown/blank dates as fresh (newly scraped) so nothing is missed
        dp = (r["date_posted"] or "").strip()
        if dp and dp < cutoff:
            continue
        out.append(dict(r))
    return out


def _open_deadlines(con, within_days: int):
    today = date.today()
    horizon = (today + timedelta(days=within_days)).isoformat()
    rows = con.execute(
        "SELECT id, company, role_title, deadline, base FROM offers "
        "WHERE status='open' AND deadline IS NOT NULL AND deadline<=? ORDER BY deadline",
        (horizon,)).fetchall()
    return [dict(r) for r in rows]


def _overdue_followups(con):
    today = date.today().isoformat()
    rows = con.execute(
        "SELECT id, contact_name, company, role_title, followup_date FROM outreach "
        "WHERE status='drafted' AND followup_date IS NOT NULL AND followup_date<=? "
        "ORDER BY followup_date", (today,)).fetchall()
    return [dict(r) for r in rows]


def _fmt_job(j: dict) -> str:
    age = j.get("date_posted") or "just scraped"
    ats = f", ATS {j['ats_score']:.0f}" if j.get("ats_score") is not None else ""
    return (f"🔥 Fresh match (pri {j['priority']:.0f}{ats}): {j['title']} @ "
            f"{j['company'] or '?'} — {j.get('location') or ''} [{j.get('market_tier') or '?'}] "
            f"posted {age}\n{j['url']}")


def _fmt_deadline(o: dict) -> str:
    return (f"⏳ Offer deadline {o['deadline']}: {o['company']} "
            f"({o['role_title'] or 'role'}, base ${o['base'] or 0:,.0f}) — decide or ask for time.")


def _fmt_followup(f: dict) -> str:
    return (f"📨 Follow-up due {f['followup_date']}: {f['contact_name']} @ {f['company']} "
            f"about {f['role_title'] or 'the role'}.")


def _post_webhook(url: str, text: str) -> bool:
    try:
        data = json.dumps({"text": text}).encode("utf-8")
        req = urllib.request.Request(url, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except Exception as exc:  # pragma: no cover - network dependent
        print(f"  ! webhook post failed: {exc}")
        return False


def run(max_age_hours: int = 24, min_priority: float = 60.0,
        tiers: list[int] | None = None, deadline_days: int = 7,
        webhook: str | None = None, dry_run: bool = False) -> dict:
    """Collect new alerts, emit them, and record them (unless dry_run)."""
    webhook = webhook or os.environ.get("JOB_BOT_WEBHOOK")
    con = connect()
    alerts: list[tuple[str, str, dict]] = []
    try:
        for j in _fresh_jobs(con, max_age_hours, min_priority, tiers):
            ref = j["url"] or f"{j['company']}|{j['title']}"
            if not _already_sent(con, "fresh_job", ref):
                alerts.append(("fresh_job", ref, j))
        for o in _open_deadlines(con, deadline_days):
            ref = f"offer-{o['id']}-{o['deadline']}"
            if not _already_sent(con, "deadline", ref):
                alerts.append(("deadline", ref, o))
        for f in _overdue_followups(con):
            ref = f"followup-{f['id']}-{f['followup_date']}"
            if not _already_sent(con, "followup", ref):
                alerts.append(("followup", ref, f))

        fmt = {"fresh_job": _fmt_job, "deadline": _fmt_deadline, "followup": _fmt_followup}
        emitted = []
        for kind, ref, obj in alerts:
            text = fmt[kind](obj)
            print("\n" + text)
            channel = "console"
            if webhook and not dry_run:
                if _post_webhook(webhook, text):
                    channel = "webhook"
            if not dry_run:
                company = obj.get("company")
                title = obj.get("title") or obj.get("role_title")
                _record(con, kind, ref, company, title, channel, text)
            emitted.append({"kind": kind, "ref": ref, "channel": channel, "text": text})
        if not dry_run:
            con.commit()
    finally:
        con.close()

    if not alerts:
        print("\nNo new alerts. (Everything fresh has already been notified.)")
    else:
        print(f"\n{len(alerts)} new alert(s)"
              + (f" → also pushed to webhook" if webhook and not dry_run else "")
              + (" [dry run — not recorded]" if dry_run else "") + ".")
    return {"count": len(alerts), "alerts": emitted if alerts else []}


def main() -> None:
    import argparse
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Notification system (Recommendation #11).")
    ap.add_argument("--max-age", type=int, default=24,
                    help="Only alert on jobs posted within N hours (default 24)")
    ap.add_argument("--min-priority", type=float, default=60.0,
                    help="Minimum job priority to alert on (default 60)")
    ap.add_argument("--tier", type=int, action="append",
                    help="Restrict to market tier(s) 1/2/3 (repeatable)")
    ap.add_argument("--deadline-days", type=int, default=7,
                    help="Alert on offer deadlines within N days (default 7)")
    ap.add_argument("--webhook", help="Slack-compatible incoming webhook URL "
                                      "(or set env JOB_BOT_WEBHOOK)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show alerts without recording or posting them")
    args = ap.parse_args()
    run(max_age_hours=args.max_age, min_priority=args.min_priority, tiers=args.tier,
        deadline_days=args.deadline_days, webhook=args.webhook, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
