"""Parse a raw job description into a structured JobPosting.

Heuristic-first (deterministic, offline). When ANTHROPIC_API_KEY is set, an
optional Claude pass enriches title/company/keywords; failures fall back to the
heuristic result.
"""

from __future__ import annotations

import re

from . import config
from .ats_platforms import detect_platform
from .jd_models import JobPosting
from .similarity import contains_phrase
from .skills_ontology import (
    KNOWN_COMPANIES,
    MARKET_TIERS,
    PREFERRED_MARKERS,
    REQUIRED_MARKERS,
    ROLE_TYPE_SIGNALS,
    SKILL_ALIASES,
    all_aliases,
)

GPA_CUTOFF_RE = re.compile(r"(?:gpa[^0-9]{0,12}|minimum[^0-9]{0,12})([23]\.\d{1,2})", re.I)
GPA_CUTOFF_RE2 = re.compile(r"([23]\.\d{1,2})\s*(?:\+\s*)?gpa", re.I)
YEARS_RE = re.compile(r"(\d{1,2})\s*\+?\s*years?", re.I)
LOCATION_RE = re.compile(r"\b([A-Z][a-zA-Z.]+(?:\s[A-Z][a-zA-Z.]+){0,2},\s*[A-Z]{2})\b")


def _present_skills(text: str) -> dict[str, int]:
    """canonical skill -> first character offset where it appears (or absence omitted)."""
    low = text.lower()
    found: dict[str, int] = {}
    for alias, canon in all_aliases():
        if canon in found:
            continue
        if contains_phrase(low, alias):
            found[canon] = low.find(alias.strip())
    return found


def _marker_positions(low: str) -> list[tuple[int, str]]:
    marks: list[tuple[int, str]] = []
    for m in PREFERRED_MARKERS:
        i = low.find(m)
        if i >= 0:
            marks.append((i, "preferred"))
    for m in REQUIRED_MARKERS:
        i = low.find(m)
        if i >= 0:
            marks.append((i, "required"))
    return sorted(marks)


def _importance_at(pos: int, marks: list[tuple[int, str]]) -> str:
    kind = "required"
    for i, k in marks:
        if i <= pos:
            kind = k
        else:
            break
    return kind


def _classify_role(skills: set[str]) -> str | None:
    best, best_score = None, 0
    for role, signals in ROLE_TYPE_SIGNALS.items():
        score = len(skills & set(signals))
        if score > best_score:
            best, best_score = role, score
    return best


def _detect_market(text: str, location: str | None) -> tuple[str | None, int | None, bool]:
    low = (location or text).lower()
    remote = bool(re.search(r"\bremote\b|\bhybrid\b|work from home|wfh", text, re.I))
    for label, cfg in MARKET_TIERS.items():
        for token in cfg["cities"] + cfg["states"]:
            if re.search(rf"(?<![a-z]){re.escape(token)}(?![a-z])", low):
                return label, cfg["tier"], remote
    return ("Remote" if remote else None), (None if not remote else 0), remote


def _seniority(text: str) -> str | None:
    low = text.lower()
    if re.search(r"\bintern(ship)?\b", low):
        return "intern"
    if re.search(r"\b(senior|sr\.|lead|principal|manager)\b", low):
        return "senior"
    if re.search(r"\b(entry[- ]level|new grad|graduate|associate|junior|jr\.)\b", low):
        return "entry"
    return "mid"


def _guess_title(text: str) -> str | None:
    for raw in text.splitlines():
        line = raw.strip(" #*-•\t")
        if not line:
            continue
        if m := re.match(r"(?:job\s*title|position|role)\s*[:\-]\s*(.+)", line, re.I):
            return m.group(1).strip()
        # otherwise first plausible title line
        if 2 <= len(line.split()) <= 9 and not line.endswith((".", ":")) and len(line) < 70:
            return line
    return None


def _guess_company(text: str) -> str | None:
    if m := re.search(r"(?:company|employer|organization)\s*[:\-]\s*(.+)", text, re.I):
        return m.group(1).splitlines()[0].strip()
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    head = "\n".join(lines[:6]).lower()
    for key, disp in KNOWN_COMPANIES.items():
        if re.search(rf"(?<![a-z]){re.escape(key)}(?![a-z])", head):
            return disp
    # "Company — Location" style second line
    if len(lines) >= 2:
        cand = re.split(r"\s[—–|·-]\s|,", lines[1])[0].strip()
        if cand[:1].isupper() and 1 <= len(cand.split()) <= 5 and len(cand) < 40:
            return cand
    if m := re.search(r"\bat\s+([A-Z][A-Za-z0-9&.\- ]{2,40})(?:[,.\n]|\s+(?:is|we|in))", text):
        return m.group(1).strip()
    return None


def parse_jd(text: str, url: str | None = None, use_llm: bool | None = None) -> JobPosting:
    text = text.strip()
    low = text.lower()

    title = _guess_title(text)
    company = _guess_company(text)
    loc_m = LOCATION_RE.search(text)
    location = loc_m.group(1) if loc_m else None

    skills_pos = _present_skills(text)
    marks = _marker_positions(low)
    required, preferred = [], []
    for canon, pos in skills_pos.items():
        if _importance_at(pos, marks) == "preferred":
            preferred.append(canon)
        else:
            required.append(canon)

    market_label, tier_num, remote = _detect_market(text, location)
    platform, how = detect_platform(url, text, company)

    gpa = None
    if m := (GPA_CUTOFF_RE.search(text) or GPA_CUTOFF_RE2.search(text)):
        try:
            gpa = float(m.group(1))
        except ValueError:
            pass
    years = None
    if m := YEARS_RE.search(text):
        years = int(m.group(1))

    job = JobPosting(
        title=title,
        company=company,
        location=location or (market_label if remote else None),
        source_url=url,
        role_type=_classify_role(set(skills_pos)),
        seniority=_seniority(text),
        market_tier=market_label,
        market_tier_num=tier_num,
        remote=remote,
        ats_platform=platform,
        ats_detection=how,
        gpa_cutoff=gpa,
        years_experience=years,
        required_keywords=sorted(required),
        preferred_keywords=sorted(preferred),
        all_keywords=sorted(skills_pos),
        raw_text=text,
    )

    if use_llm is None:
        use_llm = config.has_llm()
    if use_llm and config.has_llm():
        try:
            job = _llm_enrich(job)
        except Exception as exc:
            print(f"  ! LLM JD enrichment failed ({exc}); using heuristic parse")
    return job


def _llm_enrich(job: JobPosting) -> JobPosting:
    import json

    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    canon_list = ", ".join(sorted(SKILL_ALIASES.keys()))
    prompt = (
        "Extract fields from this job description as JSON with keys: "
        "title, company, location, required_keywords, preferred_keywords. "
        f"For keywords, ONLY use values from this controlled list: [{canon_list}]. "
        "required_keywords = must-haves; preferred_keywords = nice-to-haves.\n\n"
        f"JOB DESCRIPTION:\n{job.raw_text[:6000]}"
    )
    msg = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(b.text for b in msg.content if b.type == "text").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw).strip()
    data = json.loads(raw)
    valid = set(SKILL_ALIASES.keys())
    job.title = data.get("title") or job.title
    job.company = data.get("company") or job.company
    job.location = data.get("location") or job.location
    req = [k for k in data.get("required_keywords", []) if k in valid]
    pref = [k for k in data.get("preferred_keywords", []) if k in valid and k not in req]
    if req or pref:
        job.required_keywords = sorted(req)
        job.preferred_keywords = sorted(pref)
        job.all_keywords = sorted(set(req) | set(pref))
    return job
