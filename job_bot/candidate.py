"""Who the candidate is - read from the profile, never hardcoded.

Every prompt, template, and default that used to carry a specific person's name,
school, or graduation date goes through here instead, so the same code serves
whoever built ``data/master_profile.json``. Environment overrides exist for the
two facts a fresh clone may not have a profile for yet:

* ``JOB_BOT_CANDIDATE_NAME`` - full name used in letters, prompts and sign-offs.
* ``JOB_BOT_CANDIDATE_BLURB`` - one clause describing the candidate, e.g.
  ``an Accounting + Information Science student at the University of Maryland``.

Nothing here raises: with no profile and no overrides the helpers fall back to
neutral wording ("the candidate", "a job seeker") rather than a wrong person.
"""
from __future__ import annotations

import json
import os
import re

from . import config

_NEUTRAL_NAME = "the candidate"


def profile() -> dict:
    """The master profile as a dict, or ``{}`` if it hasn't been built yet."""
    try:
        return json.loads(config.PROFILE_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _first_education(prof: dict | None) -> dict:
    edu = (prof or {}).get("education") or [{}]
    return edu[0] if isinstance(edu[0], dict) else {}


def name(prof: dict | None = None) -> str:
    """Full name: profile ``personal.name`` > ``JOB_BOT_CANDIDATE_NAME`` > neutral."""
    prof = profile() if prof is None else prof
    return (
        (prof.get("personal") or {}).get("name")
        or os.getenv("JOB_BOT_CANDIDATE_NAME", "").strip()
        or _NEUTRAL_NAME
    )


def first_name(prof: dict | None = None) -> str:
    full = name(prof)
    return full if full == _NEUTRAL_NAME else full.split()[0]


def school(prof: dict | None = None) -> str:
    prof = profile() if prof is None else prof
    return (_first_education(prof).get("school") or "").strip()


_DEGREE_PREFIX = re.compile(
    r"^(?:bachelor|master|b\.?s\.?|b\.?a\.?|m\.?s\.?|m\.?a\.?)\b[^,:-]*(?:\s+(?:in|of)\b|[,:-])\s*",
    re.I,
)
_COLLEGE_SUFFIX = re.compile(r"\s*[-\u2013\u2014(]\s*(?:college|school|department)\b.*$", re.I)


def _clean_major(text: str) -> str:
    """'Bachelor of Science, Information Science - College of Information' -> 'Information Science'."""
    text = _DEGREE_PREFIX.sub("", (text or "").strip())
    return _COLLEGE_SUFFIX.sub("", text).strip(" ,")


def major(prof: dict | None = None) -> str:
    """'Accounting and Information Science' style phrase, or '' if unknown."""
    prof = profile() if prof is None else prof
    edu = _first_education(prof)
    primary = _clean_major(edu.get("major") or "")
    secondary = _clean_major(edu.get("secondary_major") or "")
    if primary and secondary:
        return f"{primary} and {secondary}"
    return primary or secondary


def graduation(prof: dict | None = None) -> str:
    prof = profile() if prof is None else prof
    return (_first_education(prof).get("graduation_date") or "").strip()


def blurb(prof: dict | None = None) -> str:
    """One clause for prompts: 'an Accounting student at X (graduating May 2027)'.

    Falls back to ``JOB_BOT_CANDIDATE_BLURB``, then to 'a job seeker'.
    """
    prof = profile() if prof is None else prof
    env = os.getenv("JOB_BOT_CANDIDATE_BLURB", "").strip()
    m, s, g = major(prof), school(prof), graduation(prof)
    if not (m or s):
        return env or "a job seeker"
    article = "an" if m[:1].lower() in "aeiou" else "a"
    who = f"{article} {m} student" if m else "a student"
    if s:
        who += f" at {s}"
    if g:
        who += f" (graduating {g})"
    return who


def focus(prof: dict | None = None) -> str:
    """Comma-joined target roles from the profile, or '' if none are set."""
    prof = profile() if prof is None else prof
    roles = (prof.get("targets") or {}).get("target_roles") or []
    return ", ".join(str(r) for r in roles[:3])
