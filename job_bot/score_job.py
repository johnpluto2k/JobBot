"""Phase 2 CLI: score the master profile against a job description.

Usage:
    python -m job_bot.score_job --file jd.txt
    python -m job_bot.score_job --file jd.txt --url https://boards.greenhouse.io/...
    type jd.txt | python -m job_bot.score_job          # piped via stdin
    python -m job_bot.score_job --no-llm --file jd.txt  # force heuristic parse
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import config
from .ats_engine import load_profile, score
from .jd_models import ATSScoreReport
from .jd_parser import parse_jd


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "job").lower()).strip("-")[:40] or "job"


def _bar(frac: float, width: int = 20) -> str:
    filled = int(round(frac * width))
    return "█" * filled + "░" * (width - filled)


def print_report(r: ATSScoreReport) -> None:
    j = r.job
    print("\n" + "=" * 64)
    print(f" REVERSE ATS REPORT — {j.title or 'Untitled role'}"
          + (f" @ {j.company}" if j.company else ""))
    print("=" * 64)
    loc = j.location or "—"
    tier = f" [{j.market_tier}]" if j.market_tier else ""
    print(f" Location   : {loc}{tier}" + ("  (remote/hybrid)" if j.remote else ""))
    print(f" Role type  : {j.role_type or '—'}   Seniority: {j.seniority or '—'}")
    print(f" ATS        : {r.ats_platform}  ({j.ats_detection})")
    if j.gpa_cutoff:
        print(f" GPA cutoff : {j.gpa_cutoff}")
    print("-" * 64)
    print(f" OVERALL MATCH: {r.overall_score:5.1f}/100   {r.verdict}")
    print("-" * 64)
    s = r.subscores
    print(" Subscores (platform-weighted):")
    print(f"   Keyword coverage   {_bar(s.keyword_coverage)} {s.keyword_coverage*100:4.0f}%")
    print(f"   Title alignment    {_bar(s.title_alignment)} {s.title_alignment*100:4.0f}%")
    print(f"   Quantification     {_bar(s.quantification)} {s.quantification*100:4.0f}%")
    print(f"   Content similarity {_bar(s.content_similarity)} {s.content_similarity*100:4.0f}%")
    print(f"   → {r.platform_weighting}")

    matched = [h.keyword for h in r.matched_keywords]
    print(f"\n MATCHED KEYWORDS ({len(matched)}): " + (", ".join(matched) or "—"))

    req_missing = [h.keyword for h in r.missing_keywords if h.importance == "required"]
    pref_missing = [h.keyword for h in r.missing_keywords if h.importance == "preferred"]
    print(f" MISSING — required ({len(req_missing)}): " + (", ".join(req_missing) or "none 🎉"))
    print(f" MISSING — preferred ({len(pref_missing)}): " + (", ".join(pref_missing) or "none"))

    print(f"\n {r.quantification_note}")

    if r.gap_analysis:
        print("\n RANKED GAP ANALYSIS (fix in this order):")
        for i, g in enumerate(r.gap_analysis, 1):
            tag = "REQ" if g.importance == "required" else "pref"
            print(f"  {i:>2}. [{tag}] {g.keyword}  (+{g.impact*100:.1f} pts)")
            print(f"       {g.action}")

    if r.platform_tips:
        print(f"\n {r.ats_platform} TIPS:")
        for tip in r.platform_tips:
            print(f"   • {tip}")
    print("=" * 64)


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


def main() -> None:
    # Windows consoles default to cp1252 and choke on emoji/em-dashes.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Reverse ATS score a job description (Phase 2).")
    ap.add_argument("--file", type=Path, help="Path to a job description text file")
    ap.add_argument("--text", help="Job description text inline")
    ap.add_argument("--url", help="Job posting URL (used for ATS detection)")
    ap.add_argument("--profile", type=Path, help="Path to master_profile.json")
    ap.add_argument("--no-llm", action="store_true", help="Force heuristic JD parsing")
    ap.add_argument("--json", action="store_true", help="Print JSON instead of a report")
    args = ap.parse_args()

    jd_text = _read_jd(args)
    profile = load_profile(args.profile)
    job = parse_jd(jd_text, url=args.url, use_llm=False if args.no_llm else None)
    report = score(job, profile)

    config.ensure_dirs()
    out = config.OUTPUT_DIR / f"score_{_slug(job.title or job.company)}.json"
    out.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    if args.json:
        print(report.model_dump_json(indent=2))
    else:
        print_report(report)
        print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
