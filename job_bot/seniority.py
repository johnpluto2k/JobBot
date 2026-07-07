"""Seniority detection — keep the pipeline aimed at the level John is actually at.

John is a rising senior (graduates May 2027) targeting internships and entry-level /
new-grad roles. Scraped job boards return everything, so without this filter the
pipeline fills with "Senior ...", "... Manager", "Lead ...", and roles that require
years of experience he doesn't have — and the apply gate was recommending them.

classify() reads the level from the title AND the JD text (years-of-experience
required), returning one of: intern < entry < mid < senior < lead < exec. The
search + apply gate use it to drop / down-rank anything above his target level.

Calibrated for John's fields: 'Staff Accountant' and 'Staff Auditor' are ENTRY in
accounting (so 'staff' is NOT treated as senior), while 'Senior Auditor',
'Audit Manager', and 'Analyst III' are correctly filtered out.
"""

from __future__ import annotations

import re

LEVELS = ["intern", "entry", "mid", "senior", "lead", "exec"]
_ORDER = {lvl: i for i, lvl in enumerate(LEVELS)}

# John targets internships + entry-level; 'mid' is a stretch (kept but gated), and
# senior/lead/exec are filtered out of search results and never recommended.
TARGET_MAX = "entry"          # his primary target ceiling
KEEP_MAX = "mid"              # highest level still shown (mid is a stretch, gated)

_INTERN = re.compile(r"\b(intern|internship|co-?op|apprentice(ship)?|trainee|"
                     r"fellowship|fellow|student)\b", re.I)
_EXEC = re.compile(r"\b(chief|c[etofi]o|cto|cio|ciso|vp|vice[- ]president|"
                   r"president|head of|partner|managing director|executive director)\b", re.I)
_LEAD = re.compile(r"\b(manager|mgr|director|supervisor|architect|foreman|"
                   r"team lead|tech lead|principal)\b", re.I)
# 'lead' alone, but NOT 'lead generation' / 'leads' (sales/marketing entry terms).
_LEAD_WORD = re.compile(r"\blead\b(?!\s+(generation|gen|qualification))", re.I)
# NOTE: deliberately no 'staff' — 'Staff Accountant/Auditor' are entry roles.
_SENIOR = re.compile(r"\b(senior|sr\.?|expert|specialist iii|iii|iv|vii?|"
                     r"lead\s+(?:analyst|engineer|developer|auditor|accountant))\b", re.I)
_ROMAN_MID = re.compile(r"\b(ii)\b", re.I)
_ENTRY = re.compile(r"\b(entry[- ]?level|junior|jr\.?|new[- ]?grad|graduate|"
                    r"associate|assistant|apprentice|trainee|i)\b", re.I)

_YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:to|-|–)?\s*\d{0,2}\s*(?:years?|yrs?)"
                    r"(?:\s+(?:of\s+)?(?:experience|exp|relevant))?", re.I)


def extract_years(text: str) -> int | None:
    """Largest 'N years' figure mentioned in the text (a rough required-experience)."""
    if not text:
        return None
    nums = [int(m.group(1)) for m in _YEARS.finditer(text) if m.group(1).isdigit()]
    nums = [n for n in nums if n <= 25]  # ignore '401k'-style noise / absurd values
    return max(nums) if nums else None


def _years_level(years: int | None) -> str | None:
    if years is None:
        return None
    if years <= 2:
        return "entry"
    if years <= 4:
        return "mid"
    return "senior"          # 5+ years required = not an entry candidate's role


def classify(title: str | None, text: str = "", years: int | None = None) -> str:
    """Return the seniority level of a posting from its title + JD text."""
    t = title or ""
    if _INTERN.search(t) or (text and _INTERN.search(text[:400])):
        return "intern"

    title_level: str | None = None
    if _EXEC.search(t):
        title_level = "exec"
    elif _LEAD.search(t) or _LEAD_WORD.search(t):
        title_level = "lead"
    elif _SENIOR.search(t):
        title_level = "senior"
    elif _ROMAN_MID.search(t):
        title_level = "mid"
    elif _ENTRY.search(t):
        title_level = "entry"

    if years is None:
        years = extract_years(text)
    yl = _years_level(years)

    cands = [x for x in (title_level, yl) if x]
    if not cands:
        return "entry"      # untitled / unqualified roles default to keep-able entry
    return max(cands, key=lambda x: _ORDER[x])


def is_above(level: str, ceiling: str) -> bool:
    return _ORDER.get(level, 1) > _ORDER.get(ceiling, 1)


def too_senior(level: str) -> bool:
    """Above what we ever show John (senior/lead/exec)."""
    return is_above(level, KEEP_MAX)


def label(level: str) -> str:
    return {"intern": "🎓 Internship", "entry": "🟢 Entry-level", "mid": "🟡 Mid-level",
            "senior": "🔴 Senior", "lead": "🔴 Lead/Mgr", "exec": "🔴 Executive"}.get(level, level)
