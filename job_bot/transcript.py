"""Parse a UMD (Testudo) unofficial transcript and enrich the master profile.

Pulls verified cumulative GPA, completed coursework with grades, semester
academic honors, and in-progress courses — richer and more accurate than the
short coursework list on a resume — and merges them into the education section.
"""

from __future__ import annotations

import re

from . import config
from .ingest import parse_file
from .models import Education, MasterProfile, SourceDoc

# A graded course row, e.g. "BMGT310 INTERMED ACCOUNTING I A- 3.00 3.00 11.10"
COURSE_RE = re.compile(
    r"\b([A-Z]{2,4}\d{3})\s+(.+?)\s+([A-F][+-]?|P|S|NC|XF|W)\s+\d+\.\d+\s+\d+\.\d+", re.M)
CUM_GPA_RE = re.compile(r"UG Cumulative GPA\s*:?\s*([0-4]\.\d{1,3})", re.I)
SEM_GPA_RE = re.compile(r"Semester:.*?GPA\s*([0-4]\.\d{1,3})", re.I)

# Course prefixes worth surfacing as "relevant coursework".
RELEVANT_PREFIXES = ("BMGT", "INST", "ECON", "STAT", "CMSC", "MATH140", "ENES")

# Light cleanup of UMD's abbreviated, uppercased titles.
TITLE_FIXES = {
    "Prin Accounting I": "Principles of Accounting I",
    "Prin Accounting Ii": "Principles of Accounting II",
    "Intermed Accounting I": "Intermediate Accounting I",
    "Managerial Accounting": "Managerial Accounting",
    "Business Finance": "Business Finance",
    "Obj-Orient Prog Info Sci": "Object-Oriented Programming for Information Science",
    "Object-Oriented Prog I": "Object-Oriented Programming I",
    "Database Design Modeling": "Database Design and Modeling",
    "Statistics For Info Sci": "Statistics for Information Science",
    "Information Organization": "Information Organization",
    "Orgs Mgmt Teamwork": "Organizations, Management & Teamwork",
    "Tech Infrastructure Arch": "Technology Infrastructure & Architecture",
    "User-Centered Design": "User-Centered Design",
    "Managing People And Orgs": "Managing People and Organizations",
    "Intro To Progam Info Sci": "Introduction to Programming for Information Science",
    "Intro Information Sci": "Introduction to Information Science",
    "Microeconomic Principles": "Microeconomic Principles",
    "Marketing Prin & Organiz": "Marketing Principles & Organization",
    "Info User Needs & Assess": "Information User Needs & Assessment",
    "Intermed Accounting Ii": "Intermediate Accounting II",
    "Taxation Of Individuals": "Taxation of Individuals",
    "Decision-Making Info Sci": "Decision-Making for Information Science",
    "Intro To Info Systems": "Introduction to Information Systems",
    "Intro Comp Prog Via Web": "Introduction to Computer Programming via the Web",
    "Dynamic Web Applications": "Dynamic Web Applications",
}

# Courses that aren't meaningful "coursework" to list on a resume.
COURSEWORK_BLOCKLIST = {"BMGT367", "BMGT366", "UNIV100"}


def _title(raw: str) -> str:
    t = raw.strip().title().replace("  ", " ")
    return TITLE_FIXES.get(t, t)


def parse_transcript(text: str) -> dict:
    courses: list[dict] = []
    seen: set[str] = set()
    for m in COURSE_RE.finditer(text):
        code, title, grade = m.group(1), _title(m.group(2)), m.group(3)
        if code in seen:
            continue
        seen.add(code)
        courses.append({"code": code, "title": title, "grade": grade})

    cum = CUM_GPA_RE.search(text)
    cumulative_gpa = float(cum.group(1)) if cum else None

    honors_count = len(re.findall(r"Semester Academic Honors", text))
    sem_gpas = [float(g) for g in SEM_GPA_RE.findall(text)]
    honors: list[str] = []
    if honors_count:
        best = f", best semester GPA {max(sem_gpas):.3f}" if sem_gpas else ""
        plural = "s" if honors_count != 1 else ""
        honors.append(f"Semester Academic Honors / Dean's List ({honors_count} semester{plural}"
                      f"{best})")

    # In-progress (current) courses appear in a section without quality points.
    in_progress: list[str] = []
    cur = re.search(r"Current Course Information(.+)$", text, re.S)
    if cur:
        for m in re.finditer(r"\b([A-Z]{2,4}\d{3})\b\s+\d{4}\s+\d+\.\d+\s+REG\s+A", cur.group(1)):
            in_progress.append(m.group(1))

    relevant = [c for c in courses
                if (c["code"].startswith(RELEVANT_PREFIXES) or c["code"] == "MATH140")
                and c["code"] not in COURSEWORK_BLOCKLIST]
    return {
        "cumulative_gpa": cumulative_gpa,
        "courses": courses,
        "relevant_coursework": [c["title"] for c in relevant],
        "honors": honors,
        "in_progress": sorted(set(in_progress)),
    }


def _find_transcript():
    base = config.TRANSCRIPT_DIR
    if not base.exists():
        return None
    cands = [p for p in base.rglob("*") if p.is_file()
             and p.suffix.lower() == ".pdf" and "transcript" in p.name.lower()]
    if not cands:
        return None
    return max(cands, key=lambda p: p.stat().st_mtime)


def enrich_profile(profile: MasterProfile) -> dict | None:
    """Parse the newest transcript and merge into profile.education[0]. Returns
    the parsed transcript dict (or None if no transcript found)."""
    path = _find_transcript()
    if path is None:
        return None
    doc = parse_file(path)
    if doc is None:
        return None
    data = parse_transcript(doc.text)

    if not profile.education:
        profile.education.append(Education())
    edu = profile.education[0]

    # The transcript is authoritative — use its (cleaned) coursework instead of
    # the resume's shorter, less consistent list.
    if data["relevant_coursework"]:
        edu.relevant_coursework = data["relevant_coursework"]

    for h in data["honors"]:
        if h not in edu.honors:
            edu.honors.append(h)

    # Record the verified cumulative GPA in honors context without overwriting
    # the (rounded) GPA the candidate presents on the resume.
    if data["cumulative_gpa"]:
        note = f"Verified cumulative GPA {data['cumulative_gpa']:.3f} (UMD transcript)"
        if note not in edu.honors:
            edu.honors.append(note)
        if edu.gpa is None:
            edu.gpa = round(data["cumulative_gpa"], 2)

    profile.source_documents.append(
        SourceDoc(path=str(path), filename=path.name, doc_type="transcript",
                  char_count=doc.char_count, parser=doc.parser)
    )
    return data
