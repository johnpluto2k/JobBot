"""Central configuration for the job application system.

Reads settings from environment variables (optionally loaded from a .env file).
Nothing here requires an API key; the key is only needed for LLM-backed
extraction. Without it the pipeline falls back to a heuristic parser.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional at runtime
    pass

# Project root = the "Job Bot" folder that contains this package.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _primary_checkout(root: Path) -> Path:
    """The repo's PRIMARY working tree, even when called from a git worktree.

    `data/` is gitignored, so it is not shared between worktrees - each linked
    worktree silently grows its own copy of job_bot.db and master_profile.json.
    That is not a theoretical problem: on 2026-08-31 the CowSync role was added
    to the profile from the resume-adjuster worktree, wrote to that worktree's
    private copy, and the running app never saw it. The same worktree was also
    scoring against a 122 KB near-empty database instead of the real 5.6 MB one.

    A linked worktree's `.git` is a FILE containing
    `gitdir: <primary>/.git/worktrees/<name>`, so the primary checkout can be
    recovered from it without shelling out to git. In the primary checkout
    `.git` is a directory and this returns `root` unchanged.
    """
    marker = root / ".git"
    try:
        if marker.is_file():
            text = marker.read_text(encoding="utf-8", errors="ignore").strip()
            if text.startswith("gitdir:"):
                gitdir = Path(text.split(":", 1)[1].strip())
                if not gitdir.is_absolute():
                    gitdir = (root / gitdir).resolve()
                parts = gitdir.parts
                # .../<primary>/.git/worktrees/<name> -> drop the last three parts
                if "worktrees" in parts:
                    i = parts.index("worktrees")
                    if i >= 2:
                        return Path(*parts[:i - 1])
    except OSError:
        pass
    return root


# One data directory per REPO, not per worktree. JOB_BOT_OUTPUT_DIR still wins.
DATA_HOME = _primary_checkout(PROJECT_ROOT)

def _find_dir(name: str) -> Path:
    """Locate a documents folder regardless of where it was dropped in:
    the dedicated documents/ folder (preferred), the project root, or inside
    the job_bot/ package folder (legacy)."""
    for base in (PROJECT_ROOT / "documents", PROJECT_ROOT, PROJECT_ROOT / "job_bot"):
        candidate = base / name
        if candidate.exists():
            return candidate
    return PROJECT_ROOT / "documents" / name


# Where the user's source documents live (resumes, cover letters, transcripts).
DOCS_DIR = Path(os.getenv("JOB_BOT_DOCS_DIR", _find_dir("Professional Development")))
# Transcripts / graduation plans / curriculum checklists live here.
TRANSCRIPT_DIR = Path(os.getenv("JOB_BOT_TRANSCRIPT_DIR", _find_dir("School Related Stuff")))

# Where generated artifacts are written.
OUTPUT_DIR = Path(os.getenv("JOB_BOT_OUTPUT_DIR", DATA_HOME / "data"))
PROFILE_JSON = OUTPUT_DIR / "master_profile.json"
RAW_TEXT_DIR = OUTPUT_DIR / "raw_text"
CHROMA_DIR = OUTPUT_DIR / "chroma"

# LLM settings. The plan targets claude-sonnet-5 for judgment-heavy calls
# (cover letters, extraction); mechanical calls (bullet rephrasing) route to
# the cheaper/faster model below.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
ANTHROPIC_MODEL_FAST = os.getenv("ANTHROPIC_MODEL_FAST", "claude-haiku-4-5-20251001")

# File types we know how to read.
PDF_SUFFIXES = {".pdf"}
DOCX_SUFFIXES = {".docx"}
TEXT_SUFFIXES = {".txt", ".md"}
SUPPORTED_SUFFIXES = PDF_SUFFIXES | DOCX_SUFFIXES | TEXT_SUFFIXES


def ensure_dirs() -> None:
    """Create output directories if they don't yet exist."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_TEXT_DIR.mkdir(parents=True, exist_ok=True)


def has_llm() -> bool:
    """True when an Anthropic API key is available for LLM extraction."""
    return bool(ANTHROPIC_API_KEY)
