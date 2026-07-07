"""Phase 1 pipeline entry point.

Reads every supported document under the docs folder, extracts a structured
MasterProfile (LLM when an API key is present, heuristic otherwise), optionally
stores it in ChromaDB, and writes master_profile.json — the system's source of
truth.

Usage:
    python -m job_bot.build_profile                # use default docs folder
    python -m job_bot.build_profile --docs PATH    # custom folder
    python -m job_bot.build_profile --no-llm       # force heuristic extraction
    python -m job_bot.build_profile --no-vector    # skip ChromaDB
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import config
from .extract import extract_profile
from .ingest import ingest
from .models import MasterProfile
from .store import store_profile


def build(docs_dir: Path | None = None, use_llm: bool | None = None,
          use_vector: bool = True) -> MasterProfile:
    config.ensure_dirs()

    print(f"[1/4] Ingesting documents from: {docs_dir or config.DOCS_DIR}")
    docs = ingest(docs_dir)
    if not docs:
        raise SystemExit(
            f"No supported documents found under {docs_dir or config.DOCS_DIR}. "
            "Set JOB_BOT_DOCS_DIR or pass --docs."
        )
    print(f"      parsed {len(docs)} document(s)")

    print("[2/4] Extracting structured profile")
    profile = extract_profile(docs, use_llm=use_llm)

    from .transcript import enrich_profile
    tdata = enrich_profile(profile)
    if tdata:
        print(f"      + transcript: {len(tdata['courses'])} courses, "
              f"cum GPA {tdata['cumulative_gpa']}, {len(tdata['in_progress'])} in progress")

    print("[3/4] Writing master_profile.json")
    config.PROFILE_JSON.write_text(
        profile.model_dump_json(indent=2), encoding="utf-8"
    )
    print(f"      -> {config.PROFILE_JSON}")

    print("[4/4] Storing in vector DB")
    if use_vector:
        store_profile(profile)
    else:
        print("      skipped (--no-vector)")

    _summary(profile)
    return profile


def _summary(p: MasterProfile) -> None:
    print("\n=== Profile summary ===")
    print(f"  method       : {p.extraction_method}")
    print(f"  name         : {p.personal.name}")
    print(f"  contact      : {p.personal.email} | {p.personal.phone}")
    if p.education:
        e = p.education[0]
        print(f"  education    : {e.degree or ''} @ {e.school or ''} (GPA {e.gpa}, {e.graduation_date})")
    print(f"  experience   : {len(p.experience)} roles, "
          f"{sum(len(x.bullets) for x in p.experience)} bullets")
    print(f"  leadership   : {len(p.leadership)} entries")
    print(f"  projects     : {len(p.projects)}")
    print(f"  skill groups : {len(p.skills)}")
    print(f"  certs        : {', '.join(p.certifications) or '—'}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the master profile (Phase 1).")
    ap.add_argument("--docs", type=Path, default=None, help="Documents folder")
    ap.add_argument("--no-llm", action="store_true", help="Force heuristic extraction")
    ap.add_argument("--no-vector", action="store_true", help="Skip ChromaDB storage")
    args = ap.parse_args()

    build(
        docs_dir=args.docs,
        use_llm=False if args.no_llm else None,
        use_vector=not args.no_vector,
    )


if __name__ == "__main__":
    main()
