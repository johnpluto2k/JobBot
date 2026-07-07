"""Turn parsed documents into a structured MasterProfile.

Two paths:
  * LLM extraction (preferred) — uses the Anthropic API when ANTHROPIC_API_KEY
    is set, asking Claude to return JSON matching the schema.
  * Heuristic extraction (fallback) — regex + section parsing, so the pipeline
    produces a useful profile even with no API key / offline.
"""

from __future__ import annotations

import json
import re

from . import config
from .ingest import ParsedDoc
from .models import (
    Bullet,
    Education,
    Experience,
    Leadership,
    MasterProfile,
    PersonalInfo,
    Project,
    SkillGroup,
    SourceDoc,
    Targets,
)

# Seeded from the master plan; the system refines these over time.
DEFAULT_TARGETS = Targets(
    target_roles=[
        "IT Audit / Technology Risk",
        "FinTech Operations/Risk",
        "Data Analytics / FP&A",
        "Big 4 Audit",
    ],
    target_firms=["Deloitte", "PwC", "EY", "KPMG", "Stripe", "Plaid", "Robinhood", "Block"],
    target_markets=["DMV (DC, MD, VA)", "NYC", "Remote"],
    personas=["audit", "analytics", "tech/fintech"],
)

BULLET_RE = re.compile(r"^\s*[•●▪·\-\*]\s+(.*)$")
MONTHS = (r"January|February|March|April|May|June|July|August|September|October|"
          r"November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?<!\d)(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)")
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w%-]+/?", re.I)
GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[\w%-]+/?", re.I)
GPA_RE = re.compile(r"GPA[:\s]*([0-3]\.\d{1,2}|4\.0{1,2})", re.I)
NUM_RE = re.compile(r"\d")

SECTION_HEADINGS = {
    "education": ["education"],
    "experience": ["work experience", "experience", "professional experience", "employment"],
    "leadership": ["leadership", "involvement", "activities", "extracurricular"],
    "projects": ["projects", "technical projects"],
    "skills": ["skills", "technical skills"],
    "certifications": ["certifications", "licenses"],
}

SKILL_BUCKETS: dict[str, set[str]] = {
    "technical": {
        "python", "r", "sql", "java", "javascript", "html", "css", "node", "express",
        "supabase", "postgres", "playwright", "git", "github", "tableau", "power bi",
        "chart.js", "rest", "api",
    },
    "financial": {
        "excel", "financial analysis", "fp&a", "accounting", "audit", "dcf", "valuation",
        "budgeting", "forecasting", "cpa",
    },
    "analytical": {"data analysis", "statistics", "modeling", "data modeling"},
    "soft": {"leadership", "collaboration", "communication", "teamwork", "mentoring"},
}


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def _make_bullet(text: str) -> Bullet:
    text = text.strip()
    tags = sorted({kw for bucket in SKILL_BUCKETS.values() for kw in bucket if kw in text.lower()})
    quantified = bool(re.search(r"\d", text)) and bool(
        re.search(r"[%$]|\bpercent\b|\d{2,}", text)
    )
    return Bullet(text=text, keyword_tags=tags, quantified=quantified,
                  strength_score=0.7 if quantified else 0.5)


def _source_docs(docs: list[ParsedDoc]) -> list[SourceDoc]:
    return [
        SourceDoc(
            path=str(d.path),
            filename=d.filename,
            doc_type=d.doc_type,
            char_count=d.char_count,
            parser=d.parser,
        )
        for d in docs
    ]


# --------------------------------------------------------------------------- #
# Heuristic extraction
# --------------------------------------------------------------------------- #
def _strip_md(text: str) -> str:
    """Remove markdown emphasis/code markers."""
    return re.sub(r"\*\*|__|\*|_|`|#", "", text).strip()


def _normalize_md(text: str) -> str:
    """Flatten markdown tables into plain lines so section parsing works on
    both PDF (plain text) and DOCX (markdown) extractions."""
    out: list[str] = []
    for raw in text.splitlines():
        s = raw.rstrip()
        stripped = s.strip()
        if stripped.startswith("|"):
            # Skip table separator rows like |---|---|
            if set(stripped) <= set("|-: "):
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            cells = [c for c in cells if c]
            s = "    ".join(cells)  # mimic PDF two-column spacing
        out.append(s)
    return "\n".join(out)


def _spans(line: str) -> tuple[list[str], list[str], str]:
    """Return (bold spans, italic spans, plain text) for a markdown line."""
    bold = [b.strip() for b in re.findall(r"\*\*(.+?)\*\*", line)]
    no_bold = re.sub(r"\*\*(.+?)\*\*", " ", line)
    italic = [i.strip() for i in re.findall(r"(?<!\*)_(.+?)_(?!\*)", no_bold)]
    return bold, italic, _strip_md(line)


def _is_bullet(raw: str) -> bool:
    return bool(BULLET_RE.match(raw))


def _bullet_text(raw: str) -> str:
    t = BULLET_RE.match(raw).group(1)
    t = re.sub(r"^[•●▪·\-\*]\s*", "", t)  # drop a doubled-up bullet marker
    return _strip_md(t)


def _pick_primary(docs: list[ParsedDoc]) -> ParsedDoc | None:
    """Prefer the most recently modified resume (latest GPA, latest roles)."""
    resumes = [d for d in docs if d.doc_type == "resume"]
    pool = resumes or [d for d in docs if d.doc_type != "cover_letter"] or docs
    if not pool:
        return None
    return max(pool, key=lambda d: d.path.stat().st_mtime)


def _extract_personal(text: str) -> PersonalInfo:
    info = PersonalInfo()
    if m := EMAIL_RE.search(text):
        info.email = m.group(0)
    if m := PHONE_RE.search(text):
        info.phone = m.group(0).strip()
    if m := LINKEDIN_RE.search(text):
        info.linkedin = m.group(0)
    if m := GITHUB_RE.search(text):
        info.github = m.group(0)
    # Name: first non-empty line that isn't contact info.
    for raw in text.splitlines():
        line = _strip_md(raw)
        if not line:
            continue
        if EMAIL_RE.search(line) or PHONE_RE.search(line) or "linkedin" in line.lower():
            continue
        words = line.split()
        if 1 < len(words) <= 4 and all(w[0].isalpha() for w in words if w):
            info.name = line.title() if line.isupper() else line
            break
    # Location: 'City, ST' near the top of the document.
    head = "\n".join(text.splitlines()[:8])
    if m := re.search(r"([A-Z][a-zA-Z.]+(?:\s[A-Z][a-zA-Z.]+)?,\s*[A-Z]{2})\b", head):
        info.location = m.group(1)
    return info


def _split_sections(text: str) -> dict[str, list[str]]:
    """Bucket lines under the section they fall in."""
    sections: dict[str, list[str]] = {k: [] for k in SECTION_HEADINGS}
    current: str | None = None
    for raw in text.splitlines():
        line = _strip_md(raw)
        if not line:
            continue
        low = re.sub(r"[^a-z& ]", "", line.lower()).strip()
        matched = None
        if len(line) < 45:
            for key, names in SECTION_HEADINGS.items():
                if any(low == n or low.startswith(n + " ") for n in names):
                    matched = key
                    break
        if matched:
            current = matched
            continue
        if current:
            sections[current].append(raw.rstrip())
    return sections


def _split_org_loc(s: str) -> tuple[str | None, str | None]:
    """'The Scion Group College Park, MD' -> ('The Scion Group', 'College Park, MD')."""
    s = s.strip()
    m = re.search(r",\s*([A-Z]{2})\.?\s*$", s)
    if not m:
        return (s or None), None
    state = m.group(1)
    before = s[: m.start()].rstrip()
    words = before.split()
    city_words: list[str] = []
    for w in reversed(words):
        if w[:1].isupper() and len(city_words) < 2:
            city_words.insert(0, w)
        else:
            break
    city = " ".join(city_words)
    org = before[: len(before) - len(city)].strip() if city else before
    loc = f"{city}, {state}".strip().lstrip(", ")
    return (org or None), (loc or None)


def _split_role_dates(s: str) -> tuple[str | None, str | None]:
    """'Leasing Consultant August 2025 – Present' -> ('Leasing Consultant', '...')."""
    s = s.strip()
    m = re.search(rf"\b({MONTHS})\b\.?\s*\d{{4}}", s, re.I)
    if not m:
        return (s or None), None
    role = s[: m.start()].strip(" -–—,")
    dates = s[m.start():].strip()
    return (role or None), (dates or None)


DATE_TOKEN_RE = re.compile(rf"\b({MONTHS})\b\.?\s*\d{{4}}", re.I)


def _looks_like_orgline(s: str) -> bool:
    """True if a date-less line looks like a new entry's org/title rather than
    body text (used to separate entries when bullets are unmarked)."""
    if len(s) > 60 or s.endswith((".", "!", ")")):
        return False
    if "|" in s or re.search(r",\s*[A-Z]{2}\b", s):
        return True
    words = s.split()
    caps = sum(1 for w in words if w[:1].isupper())
    return 0 < len(words) <= 7 and caps >= max(2, len(words) - 2)


def _header_split(raw: str, pending_org: str | None) -> tuple[str, str | None]:
    """Split an entry header line into (org-line, role/date-line) across the
    pipe ('Org | Role  Dates'), markdown ('**Org** _Role_'), split (org on a
    previous line), and tab/space-separated layouts."""
    bold, italic, plain = _spans(raw)
    if bold:
        sub = italic[0] if italic else (plain[len(bold[0]):].strip() or None)
        return bold[0], sub
    flat = _strip_md(raw).replace("\t", "    ")
    if "|" in flat:
        org_part, _, rest = flat.partition("|")
        return org_part.strip(), re.sub(r"\s{2,}", " ", rest).strip() or None
    if pending_org is not None:
        return _strip_md(pending_org), re.sub(r"\s{2,}", " ", flat).strip() or None
    parts = [p.strip() for p in re.split(r"\s{2,}", flat) if p.strip()]
    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])
    return flat.strip(), None


def _parse_entries(lines: list[str]) -> list[tuple[str | None, str | None, list[str]]]:
    """Group lines into (org-line, role/date-line, bullets) entries.

    Handles marked bullets ('- ...'), unmarked bullets (plain paragraphs), and
    headers that may be combined on one line, split across two, or pipe/tab
    separated. Entry boundaries are detected from date-range signatures.
    """
    entries: list[dict] = []
    pending_org: str | None = None
    for raw in lines:
        plain = _strip_md(raw)
        if not plain:
            continue
        if _is_bullet(raw):
            if not entries:
                entries.append({"org": pending_org, "sub": None, "bullets": []})
                pending_org = None
            entries[-1]["bullets"].append(_bullet_text(raw))
            continue
        if DATE_TOKEN_RE.search(plain):  # a header line
            org_line, sub_line = _header_split(raw, pending_org)
            entries.append({"org": org_line, "sub": sub_line, "bullets": []})
            pending_org = None
            continue
        # date-less, unmarked line
        if not entries:
            pending_org = raw
            continue
        last = entries[-1]
        if last["sub"] is None and not last["bullets"]:
            last["sub"] = plain  # role line in a split-header layout
        elif last["bullets"] and _looks_like_orgline(plain):
            pending_org = raw    # start of the next entry's header
        else:
            last["bullets"].append(plain)  # unmarked bullet body
    return [(e["org"], e["sub"], e["bullets"]) for e in entries
            if e["bullets"] or e["org"]]


def _parse_education(lines: list[str]) -> list[Education]:
    if not lines:
        return []
    edu = Education()
    coursework: list[str] = []
    grab_courses = False
    for raw in lines:
        line = _strip_md(raw)
        low = line.lower()
        if edu.school is None and ("university" in low or "college" in low):
            edu.school = re.split(r"\t|\s{2,}|♦|\|", line)[0].strip()
        if m := GPA_RE.search(line):
            try:
                edu.gpa = float(m.group(1))
            except ValueError:
                pass
        if m := re.search(r"(bachelor|b\.?\s?s\.?|b\.?\s?a\.?|master|m\.?\s?s\.?)\b[^\n]*",
                          line, re.I):
            degree = re.split(r"\t|\s{2,}|GPA", m.group(0))[0].strip(" -\t")
            if edu.degree is None:
                edu.degree = degree
                mm = re.search(r"(?:in|,)\s+([A-Z][a-zA-Z ]+)", degree)
                if mm:
                    edu.major = mm.group(1).strip()
            elif edu.secondary_major is None:
                edu.secondary_major = degree
        if edu.graduation_date is None and (m := re.search(
                rf"(?:expected[:\s]*)?(({MONTHS})\.?\s+\d{{4}})", line, re.I)):
            edu.graduation_date = m.group(1)
        if "coursework" in low:
            grab_courses = True
            after = line.split(":", 1)
            if len(after) > 1 and after[1].strip():
                coursework.extend(_split_list(after[1]))
            continue
        if grab_courses:
            if BULLET_RE.match(raw) or "," in line:
                content = BULLET_RE.match(raw).group(1) if BULLET_RE.match(raw) else line
                coursework.extend(_split_list(content))
    edu.relevant_coursework = [c for c in dict.fromkeys(coursework) if c]
    return [edu] if (edu.school or edu.degree) else []


def _split_list(text: str) -> list[str]:
    parts = re.split(r"[,;•]\s*", text)
    return [p.strip(" .") for p in parts if p.strip(" .")]


def _header_fields(org_line: str | None, sub_line: str | None):
    org, loc = _split_org_loc(org_line) if org_line else (None, None)
    role, dates = _split_role_dates(sub_line) if sub_line else (None, None)
    # Some layouts put role/dates in the org line and nothing in sub.
    if role is None and org and re.search(rf"\b({MONTHS})\b", org, re.I):
        org2, _ = _split_org_loc(org_line)
        role, dates = _split_role_dates(org)
    start = end = None
    is_current = False
    if dates:
        is_current = "present" in dates.lower()
        parts = re.split(r"\s*[-–—]\s*", dates)
        if len(parts) == 2:
            start, end = parts[0].strip(), parts[1].strip()
        else:
            end = dates
    return org, loc, role, start, end, is_current


def _parse_experience(lines: list[str]) -> list[Experience]:
    out: list[Experience] = []
    for org_line, sub_line, bullets in _parse_entries(lines):
        if not bullets:
            continue
        org, loc, role, start, end, is_current = _header_fields(org_line, sub_line)
        exp = Experience(
            organization=org, location=loc, role=role,
            start_date=start, end_date=end, is_current=is_current,
            bullets=[_make_bullet(b) for b in bullets],
        )
        exp.keyword_tags = sorted({t for b in exp.bullets for t in b.keyword_tags})
        out.append(exp)
    return out


def _parse_leadership(lines: list[str]) -> list[Leadership]:
    out: list[Leadership] = []
    for org_line, sub_line, bullets in _parse_entries(lines):
        if not bullets:
            continue
        org, loc, role, start, end, _is_current = _header_fields(org_line, sub_line)
        out.append(
            Leadership(
                organization=org, location=loc, role=role,
                start_date=start, end_date=end,
                bullets=[_make_bullet(b) for b in bullets],
                competencies=sorted({t for b in [_make_bullet(x) for x in bullets]
                                     for t in b.keyword_tags}),
            )
        )
    return out


def _parse_skills(lines: list[str]) -> list[SkillGroup]:
    raw_skills: list[str] = []
    for raw in lines:
        content = _bullet_text(raw) if _is_bullet(raw) else _strip_md(raw)
        content = re.sub(r"(?i)^skills?:\s*", "", content.strip())
        raw_skills.extend(_split_list(content))
    buckets: dict[str, list[str]] = {}
    for skill in dict.fromkeys(raw_skills):
        buckets.setdefault(_categorize_skill(skill), []).append(skill)
    return [SkillGroup(category=cat, skills=sk) for cat, sk in buckets.items() if sk]


def _categorize_skill(skill: str) -> str:
    low = skill.lower().strip()
    for cat, members in SKILL_BUCKETS.items():
        for m in members:
            # Exact match always; substring match only for longer tokens to
            # avoid 'r' matching inside 'leadership'/'collaboration'.
            if low == m or (len(m) >= 4 and re.search(rf"\b{re.escape(m)}\b", low)):
                return cat
    return "other"


def _parse_projects(docs: list[ParsedDoc], section_lines: list[str]) -> list[Project]:
    projects: list[Project] = []
    # Dedicated project documents.
    for d in docs:
        if d.doc_type != "project":
            continue
        lines = [l for l in d.text.splitlines() if l.strip()]
        if not lines:
            continue
        name = lines[0].split("—")[0].split("-")[0].strip()
        techs = _split_list(lines[1]) if len(lines) > 1 else []
        bullets = [_make_bullet(BULLET_RE.match(l).group(1) if BULLET_RE.match(l) else l)
                   for l in lines if len(l.strip()) > 40][:6]
        projects.append(
            Project(
                name=name or d.filename,
                description=lines[0],
                technologies=[t for t in techs if len(t) < 30],
                bullets=bullets,
            )
        )
    # Projects listed within a resume section.
    for header, _sub, bullets in _parse_entries(section_lines):
        if header:
            projects.append(
                Project(name=header, bullets=[_make_bullet(b) for b in bullets])
            )
    return projects


def heuristic_extract(docs: list[ParsedDoc]) -> MasterProfile:
    primary = _pick_primary(docs)
    profile = MasterProfile(
        targets=DEFAULT_TARGETS,
        source_documents=_source_docs(docs),
        extraction_method="heuristic",
    )
    if primary is None:
        return profile

    text = _normalize_md(primary.text)
    profile.personal = _extract_personal(text)
    sections = _split_sections(text)
    profile.education = _parse_education(sections.get("education", []))
    profile.experience = _parse_experience(sections.get("experience", []))
    profile.leadership = _parse_leadership(sections.get("leadership", []))
    profile.skills = _parse_skills(sections.get("skills", []))
    profile.projects = _parse_projects(docs, sections.get("projects", []))
    profile.certifications = [
        _bullet_text(l) if _is_bullet(l) else _strip_md(l)
        for l in sections.get("certifications", [])
    ]
    # CPA eligibility appears in education text but not as a section heading.
    if "cpa" in primary.text.lower() and "CPA Eligibility" not in profile.certifications:
        profile.certifications.append("CPA Eligibility (Expected)")
    return profile


# --------------------------------------------------------------------------- #
# LLM extraction
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = """You are an expert resume parser for a personal career system.
Extract a structured profile from the candidate's documents. Rules:
- Never invent facts. Only use what is present in the documents.
- Write each accomplishment bullet in Google XYZ style when the source allows
  ("Accomplished X as measured by Y by doing Z"), but keep the real numbers.
- Tag each bullet with the concrete skills/keywords it evidences.
- Mark quantified=true when a bullet contains a metric ($, %, counts).
- Return ONLY valid JSON matching the provided schema. No prose, no markdown."""


def _llm_extract(docs: list[ParsedDoc]) -> MasterProfile:
    import anthropic  # imported lazily so the package works without the dep

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    combined = "\n\n".join(
        f"===== DOCUMENT: {d.filename} (type={d.doc_type}) =====\n{d.text}" for d in docs
    )
    schema = MasterProfile.model_json_schema()
    user = (
        "Extract the master profile as JSON conforming to this JSON schema "
        "(omit source_documents/generated_at/extraction_method — those are filled "
        f"automatically):\n\n{json.dumps(schema)}\n\n"
        f"DOCUMENTS:\n{combined}"
    )

    msg = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(block.text for block in msg.content if block.type == "text").strip()
    # Strip accidental code fences.
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    data = json.loads(text)
    data.pop("source_documents", None)
    data.pop("generated_at", None)
    profile = MasterProfile.model_validate(data)
    profile.source_documents = _source_docs(docs)
    profile.extraction_method = "llm"
    if not profile.targets.target_roles:
        profile.targets = DEFAULT_TARGETS
    return profile


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def extract_profile(docs: list[ParsedDoc], use_llm: bool | None = None) -> MasterProfile:
    """Build a MasterProfile from parsed documents.

    use_llm: force on/off. Default = auto (use LLM when an API key is set).
    """
    if use_llm is None:
        use_llm = config.has_llm()
    if use_llm and config.has_llm():
        try:
            print("  extracting with Claude API ...")
            return _llm_extract(docs)
        except Exception as exc:
            print(f"  ! LLM extraction failed ({exc}); falling back to heuristic")
    else:
        print("  no API key -> using heuristic extractor")
    return heuristic_extract(docs)
