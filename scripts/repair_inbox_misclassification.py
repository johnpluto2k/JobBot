#!/usr/bin/env python3
"""Repair the damage done by the old inbox classifier.

Context (2026-09-02): three bugs in `job_bot/inbox.py` combined to turn consumer
marketing email into job offers.

  1. `is_noise()` had no pattern for promotional mail, so Hilton Honors /
     Codecademy / Coinbase / Amex / PerkSpot blasts were treated as recruiting mail.
  2. The "offer" signal list led with a bare r"\\boffer\\b", which matches
     "make the most of this 160K Bonus Points offer".
  3. `detect_company()` fell back to the FIRST domain label, so h5.hilton.com
     became "H5" and mail.coinbase.com became "Mail"; short aliases like "EY" were
     matched anywhere in the body, so Hilton mail was attributed to EY and BDO.

Those misclassifications then hit an unbounded
`UPDATE jobs SET status=? WHERE lower(company) LIKE '%name%'`, which rewrote job
rows in place - "Itr" matched MITRE and Citrin Cooperman, "EY" matched Morgan
Stanley, Berkley, Eagle Eye, ICEYE and Kearney.

SCOPE - deliberately narrow. `tracked_emails` stores only sender and subject, not
bodies, and the original verdicts were computed WITH the body. Re-classifying every
row from the subject alone would downgrade ~166 genuine rejections and interview
invites to "other" (verified: an early version of this script did exactly that).
So this script only touches what can be proven wrong from the subject line:

  * `tracked_emails` rows currently categorised 'offer' whose subject shows no
    employment-offer language under the corrected patterns. A real offer email
    says so in the subject; a Hilton points blast does not.
  * `jobs` rows parked on status='offer' that no surviving offer email supports.
    Only scraped postings are reset - rows in the manual application ledger
    (site in email/tracker/ledger) are never rewritten, because that is John's
    real application history.

Rejection / interview / recruiter_reply rows are left alone entirely. There is no
evidence they are wrong and no body text left to re-judge them with.

Usage:  python scripts/repair_inbox_misclassification.py [--apply]
        (default is a dry run that changes nothing)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from job_bot import inbox  # noqa: E402
from job_bot.applications import canon  # noqa: E402
from job_bot.db import connect  # noqa: E402

LEDGER_SITES = ("email", "tracker", "ledger")


def _canon(name: str | None) -> str:
    return (canon(name or "") or "").strip().lower()


def _is_real_offer_subject(subject: str, sender: str) -> bool:
    """True only if the subject alone still reads as an employment offer."""
    if inbox.is_noise(subject, ""):
        return False
    return inbox.classify_email(subject, "", sender)["category"] == "offer"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    args = ap.parse_args()

    con = connect()

    # ---- 1. Bogus 'offer' emails -----------------------------------------
    offer_rows = con.execute(
        "SELECT id, sender, subject, company FROM tracked_emails WHERE category='offer' ORDER BY id"
    ).fetchall()

    bogus, genuine = [], []
    for r in offer_rows:
        (genuine if _is_real_offer_subject(r["subject"] or "", r["sender"] or "") else bogus).append(r)

    print(f"tracked_emails categorised 'offer': {len(offer_rows)}")
    print(f"  keeping as offers : {len(genuine)}")
    for r in genuine:
        print(f"      #{r['id']:<5} {(r['company'] or '?'):<16} | {(r['subject'] or '')[:56]}")
    print(f"  demoting to other : {len(bogus)}")
    for r in bogus:
        print(f"      #{r['id']:<5} {(r['company'] or '?'):<16} | {(r['subject'] or '')[:56]}")

    if args.apply and bogus:
        con.execute(
            "UPDATE tracked_emails SET category='other', company=NULL, "
            "action='Promotional/newsletter mail; not tracked.' WHERE id IN (%s)"
            % ",".join("?" * len(bogus)),
            [r["id"] for r in bogus],
        )

    # Companies that still have a genuine offer email behind them.
    offer_companies = {_canon(r["company"]) for r in genuine if r["company"]}

    # ---- 2. jobs rows still parked on a bogus 'offer' --------------------
    jobs = con.execute("SELECT id, company, title, site, status FROM jobs WHERE status='offer'").fetchall()

    to_reset, kept_ledger, kept_supported = [], 0, 0
    for j in jobs:
        if (j["site"] or "") in LEDGER_SITES:
            kept_ledger += 1
        elif _canon(j["company"]) in offer_companies:
            kept_supported += 1
        else:
            to_reset.append(j)

    print()
    print(f"jobs rows with status='offer': {len(jobs)}")
    print(f"  kept (manual ledger row)     : {kept_ledger}")
    print(f"  kept (a real offer email)    : {kept_supported}")
    print(f"  reset to 'new' (unsupported) : {len(to_reset)}")
    for j in to_reset[:12]:
        print(f"      #{j['id']:<6} {(j['company'] or '')[:26]:<26} site={j['site']}")
    if len(to_reset) > 12:
        print(f"      ...and {len(to_reset) - 12} more")

    if args.apply and to_reset:
        ids = [j["id"] for j in to_reset]
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            con.execute("UPDATE jobs SET status='new' WHERE id IN (%s)"
                        % ",".join("?" * len(chunk)), chunk)

    if args.apply:
        con.commit()
        print("\nAPPLIED.")
    else:
        print("\nDry run - nothing written. Re-run with --apply to commit.")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
