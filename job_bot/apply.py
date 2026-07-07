"""Phase 8 CLI: assisted application autofill + status tracking.

    python -m job_bot.apply --answers                 # print a copy-paste answer sheet
    python -m job_bot.apply --url "https://..."        # open + autofill (no submit)
    python -m job_bot.apply --url "https://..." --headless --screenshot
    python -m job_bot.apply --status applied --job-url "https://..."   # track status

Safety: never auto-submits unless you pass --submit. Use it for forms you are
authorized to fill, and always review before submitting.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config
from .ats_engine import load_profile
from .autofill import answer_sheet, autofill_url, mark_status


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Assisted application autofill (Phase 8).")
    ap.add_argument("--url", help="Application URL to open and autofill")
    ap.add_argument("--profile", type=Path)
    ap.add_argument("--answers", action="store_true", help="Print a copy-paste answer sheet")
    ap.add_argument("--headless", action="store_true", help="Run the browser headless")
    ap.add_argument("--screenshot", action="store_true", help="Save a screenshot after filling")
    ap.add_argument("--submit", action="store_true", help="Actually submit (off by default!)")
    ap.add_argument("--status", help="Mark a job's status: applied/networking/interview/rejected/offer")
    ap.add_argument("--job-url", help="Job URL whose status to update (with --status)")
    args = ap.parse_args()

    if args.status:
        url = args.job_url or args.url
        if not url:
            raise SystemExit("--status needs --job-url (the posting URL stored in the jobs table).")
        ok = mark_status(url, args.status)
        print(f"{'Updated' if ok else 'No matching job for'} {url} → status='{args.status}'.")
        return

    profile = load_profile(args.profile)

    if args.answers or not args.url:
        sheet = answer_sheet(profile)
        out = config.OUTPUT_DIR / "answer_sheet.md"
        config.ensure_dirs()
        out.write_text(sheet, encoding="utf-8")
        print(sheet)
        print(f"\nSaved {out}")
        if not args.url:
            print("\nProvide --url to open and autofill an application form.")
        return

    shot = (config.OUTPUT_DIR / "application_preview.png") if args.screenshot else None
    print(f"Opening {args.url} and autofilling (submit={args.submit}) ...")
    result = autofill_url(args.url, profile, submit=args.submit,
                          headless=args.headless, screenshot=shot)
    if not result["ok"]:
        print(f"  ! {result['reason']}")
        print("  Falling back to the answer sheet:\n")
        print(answer_sheet(profile))
        return
    print(f"\nFilled {len(result['filled'])} field(s):")
    for f in result["filled"]:
        print(f"   • {f}")
    if shot:
        print(f"\nScreenshot: {shot}")
    if not args.submit:
        print("\nReview the form in the browser and submit manually "
              "(re-run with --submit only if you're sure).")


if __name__ == "__main__":
    main()
