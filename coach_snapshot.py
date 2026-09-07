#!/usr/bin/env python3
"""Print the same read-only coaching snapshot used by the dashboard.

Usage: py -3 coach_snapshot.py "<Job Bot checkout>"
"""
import json
import sys
from pathlib import Path


def main() -> None:
    repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent
    sys.path.insert(0, str(repo))
    from job_bot.coach import build_snapshot

    print(json.dumps(build_snapshot(), indent=2, default=str))


if __name__ == "__main__":
    main()
