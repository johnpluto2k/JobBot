"""`python -m job_bot` (or `job-bot` once installed): the front door.

    python -m job_bot demo      # open the dashboard on fictional data
    python -m job_bot serve     # open the dashboard on your data
    python -m job_bot doctor    # check what is set up and what is missing

Every other tool keeps its own entry point (`python -m job_bot.build_profile`,
`python -m job_bot.intake`, ...); the README lists them.

This file imports nothing from the package at module level. `demo` has to set
JOB_BOT_OUTPUT_DIR before `job_bot.config` is first imported, because the
database and token paths are fixed at import time.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
DIST = WEB / "dist"


def _utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _build_ui(force: bool = False) -> bool:
    """Make sure web/dist exists. Returns False when it could not be built."""
    if DIST.is_dir() and not force:
        return True
    npm = shutil.which("npm")
    if not npm:
        print("  The dashboard UI has not been built and Node.js was not found.\n"
              "  Install Node 20+ (https://nodejs.org), then run this command again.")
        return False
    print("  Building the dashboard UI (first run only, about a minute)...")
    try:
        if not (WEB / "node_modules").is_dir():
            subprocess.run([npm, "install", "--no-audit", "--no-fund"], cwd=WEB, check=True)
        subprocess.run([npm, "run", "build"], cwd=WEB, check=True)
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"  UI build failed: {exc}\n  Try it by hand: cd web && npm install && npm run build")
        return False
    return DIST.is_dir()


def _serve(port: int, open_browser: bool) -> int:
    try:
        import uvicorn
    except ImportError:
        print("  uvicorn is not installed. Run: pip install -r requirements.txt")
        return 1
    if not _build_ui():
        return 1
    url = f"http://localhost:{port}"
    print(f"\n  Job Bot is running at {url}   (Ctrl+C to stop)\n")
    if open_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    # 127.0.0.1 only: this is a single-user app holding one person's job search.
    uvicorn.run("job_bot.api:app", host="127.0.0.1", port=port, log_level="warning")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    return _serve(args.port, not args.no_browser)


def cmd_demo(args: argparse.Namespace) -> int:
    out = ROOT / "demo_data"
    # Set before job_bot.config is imported. An existing variable wins over .env
    # (python-dotenv does not override), so these also keep a real Google client
    # or season filter in .env out of the demo.
    os.environ["JOB_BOT_OUTPUT_DIR"] = str(out)
    os.environ["GOOGLE_CLIENT_ID"] = ""
    os.environ["GOOGLE_CLIENT_SECRET"] = ""
    os.environ["JOB_BOT_TRACKER_SINCE"] = ""

    from . import demo

    if args.reset or not demo.is_seeded(out):
        result = demo.seed(out, reset=True)
        print(f"  Demo data written to {out}")
        print(f"  {result['total']} companies, {result['positions']} positions: {result['by_status']}")
    else:
        print(f"  Using existing demo data in {out}  (--reset rebuilds it)")
    print("  Everything in the demo is fictional. Your own data/ folder is not read or written.")
    if args.seed_only:
        return 0
    return _serve(args.port, not args.no_browser)


def cmd_doctor(_: argparse.Namespace) -> int:
    from . import config

    rows: list[tuple[str, str, str]] = []   # (state, label, detail)

    def add(ok: bool | None, label: str, detail: str = "") -> None:
        rows.append(({True: "ok", False: "MISSING", None: "optional"}[ok], label, detail))

    def has(module: str) -> bool:
        return importlib.util.find_spec(module) is not None

    v = sys.version_info
    add(v >= (3, 12), f"Python {v.major}.{v.minor}", "" if v >= (3, 12) else "3.12 or newer is required")
    core = ["pydantic", "fastapi", "uvicorn", "dotenv", "requests", "docx", "fitz", "reportlab"]
    missing = [m for m in core if not has(m)]
    add(not missing, "Core Python packages",
        f"missing: {', '.join(missing)}. Run: pip install -r requirements.txt" if missing else "")
    add(DIST.is_dir(), "Dashboard UI built (web/dist)",
        "" if DIST.is_dir() else "`python -m job_bot serve` builds it, or: cd web && npm install && npm run build")
    add(bool(shutil.which("node")) or None, "Node.js", "only needed to build the UI")
    add((ROOT / ".env").exists() or None, ".env", "copy .env.example to .env to add keys")

    add(config.PROFILE_JSON.exists(), "Profile (master_profile.json)",
        str(config.PROFILE_JSON) if config.PROFILE_JSON.exists()
        else "put your résumé in documents/ and run: python -m job_bot.build_profile")
    db_path = config.OUTPUT_DIR / "job_bot.db"
    add(db_path.exists() or None, "Database", str(db_path) if db_path.exists()
        else "created the first time you log an application")

    add(config.has_llm() or None, "Anthropic API key",
        "LLM tailoring, cover letters and the dashboard coach are on" if config.has_llm()
        else "without it: heuristic extraction, template letters, no dashboard coach")
    from . import google_auth

    if google_auth.configured():
        token = google_auth.token_record()
        add(bool(token) and google_auth.gmail_granted(token), "Google sign-in + Gmail sync",
            "signed in with Gmail access" if token and google_auth.gmail_granted(token)
            else "client configured; sign in at the dashboard and tick the Gmail permission")
    else:
        add(None, "Google sign-in + Gmail sync",
            "not configured: the dashboard opens in local mode and you log applications by hand")

    data_home = config.DATA_HOME
    for name in ("COACH.md", "COACH_STATE.md"):
        add((data_home / name).exists() or None, name,
            "" if (data_home / name).exists() else f"copy templates/{name.replace('.md', '.template.md')} to use the coach")
    for module, what in (("rendercv", "RenderCV résumé renderer"), ("playwright", "browser autofill"),
                         ("jobspy", "Find Jobs search"), ("apscheduler", "background Gmail sync and watcher")):
        add(has(module) or None, what, "" if has(module) else "pip install -r requirements-extras.txt")

    width = max(len(label) for _, label, _ in rows)
    print()
    for state, label, detail in rows:
        mark = {"ok": "[ok]", "MISSING": "[!!]", "optional": "[  ]"}[state]
        print(f"  {mark} {label.ljust(width)}  {detail}")
    blockers = [label for state, label, _ in rows if state == "MISSING"]
    print()
    if blockers:
        print(f"  Fix first: {'; '.join(blockers)}")
        print("  To look around before setting anything up: python -m job_bot demo")
        return 1
    print("  Ready. Start it with: python -m job_bot serve")
    return 0


def main(argv: list[str] | None = None) -> int:
    _utf8_console()
    ap = argparse.ArgumentParser(
        prog="job-bot", description="A local-first operating system for a job search.")
    sub = ap.add_subparsers(dest="command")

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--port", type=int, default=8000)
        p.add_argument("--no-browser", action="store_true", help="don't open a browser tab")

    p = sub.add_parser("serve", help="start the dashboard on your data")
    common(p)
    p.set_defaults(fn=cmd_serve)

    p = sub.add_parser("demo", help="start the dashboard on fictional demo data")
    common(p)
    p.add_argument("--reset", action="store_true", help="rebuild the demo data from scratch")
    p.add_argument("--seed-only", action="store_true", help="write the demo data and exit")
    p.set_defaults(fn=cmd_demo)

    p = sub.add_parser("doctor", help="check what is set up and what is missing")
    p.set_defaults(fn=cmd_doctor)

    args = ap.parse_args(argv)
    if not args.command:
        ap.print_help()
        return 0
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
