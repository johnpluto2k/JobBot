"""Connection data: import, store, and score networking leverage per company.

Import your real network from a LinkedIn data export
(Settings → Get a copy of your data → Connections), which produces a CSV with
columns: First Name, Last Name, Company, Position, Connected On. An optional
'Relationship' column lets you tag warmer ties (recruiter, pse, umd, ...).
"""

from __future__ import annotations

import csv
import re
import sqlite3
from pathlib import Path

from .db import connect
from .decision_models import ConnectionMatch

# relationship -> default warmth (0..1)
RELATIONSHIP_WARMTH: dict[str, float] = {
    "recruiter": 0.70,
    "first_degree": 0.75,
    "second_degree": 0.45,
    "pse": 0.55,        # Pi Sigma Epsilon — strong professional-fraternity tie
    "iefs": 0.50,
    "terptax": 0.50,
    "umd": 0.40,        # UMD alum, no direct relationship
    "alum": 0.35,
}

_SUFFIX_RE = re.compile(
    r"\b(inc|incorporated|llc|llp|l\.l\.p|ltd|limited|corp|corporation|co|company|"
    r"group|holdings|plc|the)\b", re.I
)


def normalize_company(name: str | None) -> str:
    if not name:
        return ""
    n = name.lower()
    n = _SUFFIX_RE.sub(" ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def warmth_for(relationship: str) -> float:
    return RELATIONSHIP_WARMTH.get(relationship.lower().strip(), 0.35)


def add_connection(con: sqlite3.Connection, *, name: str, company: str,
                   title: str | None = None, relationship: str = "first_degree",
                   warmth: float | None = None, location: str | None = None,
                   notes: str | None = None, source: str = "manual") -> None:
    con.execute(
        "INSERT INTO connections (name, company, company_norm, title, relationship, "
        "warmth, location, notes, source) VALUES (?,?,?,?,?,?,?,?,?)",
        (name, company, normalize_company(company), title, relationship,
         warmth if warmth is not None else warmth_for(relationship), location, notes, source),
    )


# Flexible column detection so any roster (LinkedIn export, PSE alumni sheet,
# UMD directory, ...) imports without reformatting. Lowercased header -> field.
COLUMN_ALIASES: dict[str, list[str]] = {
    "first": ["first name", "firstname", "first"],
    "last": ["last name", "lastname", "last", "surname"],
    "name": ["name", "full name", "fullname", "member name", "member", "contact"],
    "company": ["company", "employer", "organization", "organisation", "current company",
                "current employer", "company name", "firm", "workplace"],
    "title": ["position", "title", "job title", "role", "current position", "job"],
    "location": ["location", "city", "region", "area"],
    "email": ["email", "e-mail", "email address"],
    "linkedin": ["linkedin", "linkedin url", "profile", "linkedin profile"],
    "relationship": ["relationship", "tie", "tag", "group"],
    "connected": ["connected on", "connected", "date", "grad year", "class year",
                  "class", "year"],
}


def _clean(val) -> str:
    """Coerce any cell (str, number, NaN, None) to a trimmed string ('' if empty)."""
    if val is None:
        return ""
    s = str(val).strip()
    return "" if s.lower() in ("nan", "nat", "none") else s


def _pick(row: dict, field: str) -> str:
    for alias in COLUMN_ALIASES.get(field, []):
        for key, val in row.items():
            if key and str(key).strip().lower() == alias:
                cleaned = _clean(val)
                if cleaned:
                    return cleaned
    return ""


def _row_name(row: dict) -> str:
    full = _pick(row, "name")
    if full:
        return full
    first, last = _pick(row, "first"), _pick(row, "last")
    return " ".join(x for x in [first, last] if x)


def import_records(records: list[dict], *, default_relationship: str = "first_degree",
                   source: str = "import") -> int:
    """Import already-parsed rows (used by both the CLI and the dashboard uploader)."""
    con = connect()
    count = 0
    try:
        for row in records:
            company = _pick(row, "company")
            if not company:
                continue
            rel = (_pick(row, "relationship") or default_relationship) or default_relationship
            email = _pick(row, "email")
            connected = _pick(row, "connected")
            linkedin = _pick(row, "linkedin")
            class_note = f"Class {connected}" if connected and connected.isdigit() else connected
            notes = "  ".join(x for x in [class_note, email, linkedin] if x) or None
            add_connection(
                con, name=_row_name(row) or "(unknown)", company=company,
                title=_pick(row, "title") or None, relationship=rel.lower(),
                location=_pick(row, "location") or None, source=source, notes=notes,
            )
            count += 1
        con.commit()
    finally:
        con.close()
    return count


def import_linkedin_csv(path: Path, default_relationship: str = "first_degree") -> int:
    """Import a LinkedIn Connections.csv or any compatible roster. Returns rows imported."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        # LinkedIn (and some exports) prepend note lines before the header; find it.
        lines = f.readlines()
    start = 0
    for i, line in enumerate(lines):
        low = line.lower()
        if ("company" in low or "employer" in low or "organization" in low) and \
           ("name" in low or "position" in low or "title" in low):
            start = i
            break
    reader = csv.DictReader(lines[start:])
    return import_records(list(reader), default_relationship=default_relationship,
                          source=path.name)


def matches_for_company(con: sqlite3.Connection, company: str | None) -> list[ConnectionMatch]:
    if not company:
        return []
    target = normalize_company(company)
    if not target:
        return []
    out: list[ConnectionMatch] = []
    for row in con.execute("SELECT * FROM connections"):
        cn = row["company_norm"] or ""
        if not cn:
            continue
        # match if either normalized name contains the other (token-safe)
        if target == cn or target in cn or cn in target:
            out.append(ConnectionMatch(
                name=row["name"], company=row["company"], title=row["title"],
                relationship=row["relationship"], warmth=row["warmth"], notes=row["notes"],
            ))
    out.sort(key=lambda m: m.warmth, reverse=True)
    return out


def connection_strength(matches: list[ConnectionMatch]) -> tuple[float, bool]:
    """Combine matches into a 0..1 leverage score with diminishing returns.
    Returns (strength, recruiter_available)."""
    if not matches:
        return 0.0, False
    strongest = max(m.warmth for m in matches)
    extra = 0.07 * (len(matches) - 1)
    strength = min(1.0, strongest + extra)
    recruiter = any(m.relationship == "recruiter" for m in matches)
    if recruiter:
        strength = max(strength, 0.65)
    return round(strength, 3), recruiter
