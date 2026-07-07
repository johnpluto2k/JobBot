"""Tailoring engine: select + reorder + (optionally) rewrite the strongest,
most JD-relevant material from the master profile into a one-page resume.

Never fabricates — it only repositions and rewords real experience. Bullet
rewriting uses Claude when an API key is present; otherwise originals are kept
verbatim (light cleanup only).
"""

from __future__ import annotations

import re as _re
from datetime import date as _date

from . import config
from .jd_models import JobPosting
from .resume_models import TailoredEducation, TailoredResume, TailoredRole
from .similarity import contains_phrase, tfidf_cosine
from .skills_ontology import SKILL_ALIASES
from .writing_style import RESUME_BULLET_RULES, STYLE_RULES, polish_bullet

MAX_BULLETS = {"experience": 3, "leadership": 2, "projects": 4}
MAX_ROLES = {"experience": 4, "leadership": 2, "projects": 2}


def _fname_part(text: str | None) -> str:
    """Filesystem-safe token: keep alphanumerics, collapse the rest to a single
    hyphen, preserve case ("DXC Technology" -> "DXC-Technology")."""
    return _re.sub(r"[^A-Za-z0-9]+", "-", (text or "").strip()).strip("-")


def resume_basename(name: str | None, company: str | None,
                    when: str | None = None) -> str:
    """Download/save basename: ``Lastname_Firstname_Company_YYYY-MM-DD`` (no
    extension). Empty parts are dropped so it never leaves stray underscores."""
    words = (name or "").split()
    first = words[0] if words else ""
    last = words[-1] if len(words) > 1 else ""
    bits = [_fname_part(last), _fname_part(first),
            _fname_part(company), when or _date.today().isoformat()]
    return "_".join(b for b in bits if b) or "resume"


def _jd_aliases(job: JobPosting) -> set[str]:
    out: set[str] = set()
    for kw in job.all_keywords:
        out.update(SKILL_ALIASES.get(kw, [kw]))
    return out


def _bullet_relevance(bullet: dict, jd_aliases: set[str], jd_text: str) -> float:
    text = bullet.get("text", "")
    low = text.lower()
    kw_hits = sum(1 for a in jd_aliases if contains_phrase(low, a))
    sim = tfidf_cosine(text, jd_text) if jd_text else 0.0
    strength = bullet.get("strength_score", 0.5)
    return 0.5 * min(1.0, kw_hits / 2.0) + 0.3 * sim + 0.2 * strength


def _dates(entry: dict) -> str | None:
    s, e = entry.get("start_date"), entry.get("end_date")
    if s and e:
        return f"{s} – {e}"
    return e or s


def _select_role(entry: dict, kind: str, jd_aliases: set[str], jd_text: str) -> tuple[TailoredRole, float]:
    bullets = entry.get("bullets", [])
    scored = sorted(bullets, key=lambda b: _bullet_relevance(b, jd_aliases, jd_text), reverse=True)
    top = scored[: MAX_BULLETS[kind]]
    # preserve a natural reading order within the kept set
    kept_texts = [b.get("text", "") for b in top]
    role = TailoredRole(
        role=entry.get("role") or entry.get("name"),
        organization=entry.get("organization"),
        location=entry.get("location"),
        dates=_dates(entry),
        bullets=kept_texts,
    )
    role_rel = max((_bullet_relevance(b, jd_aliases, jd_text) for b in top), default=0.0)
    return role, role_rel


def _is_project_meta_bullet(text: str, name: str, techs: list[str]) -> bool:
    """True for a "bullet" that merely restates the project title or its tech
    stack. Those belong in the header (built from `name` + `technologies`); left
    in the bullet list they render as a duplicate project heading + tech line.
    Guards against a common profile-import artifact (title/tech captured as bullets)."""
    t = (text or "").strip()
    if not t:
        return True
    low = t.lower()
    if name and (low == name.lower()
                 or low.startswith(name.lower() + " ")
                 or low.startswith(name.lower() + "—")
                 or low.startswith(name.lower() + " —")
                 or low.startswith(name.lower() + " -")):
        return True  # title echo, e.g. "Pantry Plate — Full-stack recipe app"
    # tech-stack echo: a comma list whose parts are mostly the project's own techs
    parts = [p.strip().lower() for p in t.split(",") if p.strip()]
    techset = {x.strip().lower() for x in techs}
    if len(parts) >= 3 and sum(1 for p in parts if p in techset) >= 0.6 * len(parts):
        return True
    return False


def _select_project(entry: dict, jd_aliases: set[str], jd_text: str) -> tuple[TailoredRole, float]:
    techs = entry.get("technologies", [])
    name = entry.get("name") or "Project"
    bullets = [b for b in entry.get("bullets", [])
               if not _is_project_meta_bullet(b.get("text", ""), name, techs)]
    scored = sorted(bullets, key=lambda b: _bullet_relevance(b, jd_aliases, jd_text), reverse=True)
    top = scored[: MAX_BULLETS["projects"]]
    if techs:
        name = f"{name} — {', '.join(techs[:6])}"
    role = TailoredRole(role=entry.get("name"), organization=name,
                        bullets=[b.get("text", "") for b in top])
    rel = max((_bullet_relevance(b, jd_aliases, jd_text) for b in top), default=0.0)
    return role, rel


def _order_skills(profile: dict, job: JobPosting) -> list[str]:
    all_skills = [s for g in profile.get("skills", []) for s in g.get("skills", [])]
    jd_kw = set(job.all_keywords)
    matching = [s for s in all_skills if any(
        s.lower() == a or a in s.lower() for kw in jd_kw for a in SKILL_ALIASES.get(kw, [kw]))]
    rest = [s for s in all_skills if s not in matching]
    return matching + rest


def _summary(profile: dict, job: JobPosting, top_skills: list[str]) -> str:
    edu = (profile.get("education") or [{}])[0]
    grad = edu.get("graduation_date") or ""
    role = job.role_type or job.title or "the role"
    skills = ", ".join(top_skills[:4]) or "data analysis and finance"
    major = edu.get("major") or "Accounting & Information Science"
    return (f"{major} student (UMD, graduating {grad}) targeting {role}. "
            f"Strengths in {skills} — combining technical skills with client "
            f"service, compliance, & business problem-solving.").strip()


def tailor_resume(profile: dict, job: JobPosting, use_llm: bool | None = None) -> TailoredResume:
    jd_aliases = _jd_aliases(job)
    jd_text = job.raw_text

    experiences: list[tuple[TailoredRole, float]] = [
        _select_role(e, "experience", jd_aliases, jd_text) for e in profile.get("experience", [])
    ]
    # keep reverse-chronological order (as stored) but cap count
    experiences = experiences[: MAX_ROLES["experience"]]

    leadership = sorted(
        (_select_role(l, "leadership", jd_aliases, jd_text) for l in profile.get("leadership", [])),
        key=lambda x: x[1], reverse=True,
    )[: MAX_ROLES["leadership"]]

    projects = sorted(
        (_select_project(p, jd_aliases, jd_text) for p in profile.get("projects", [])),
        key=lambda x: x[1], reverse=True,
    )[: MAX_ROLES["projects"]]

    skills = _order_skills(profile, job)
    summary = _summary(profile, job, skills)

    personal = profile.get("personal", {})
    contact_bits = [personal.get("phone"), personal.get("email"),
                    personal.get("linkedin"), personal.get("location")]
    contact_line = "  •  ".join(b for b in contact_bits if b)

    edu_out = [
        TailoredEducation(
            school=e.get("school"), degree=e.get("degree"),
            secondary=e.get("secondary_major"), gpa=e.get("gpa"),
            graduation_date=e.get("graduation_date"),
            coursework=e.get("relevant_coursework", [])[:8],
        )
        for e in profile.get("education", [])
    ]

    resume = TailoredResume(
        name=personal.get("name"),
        contact_line=contact_line,
        summary=summary,
        education=edu_out,
        experience=[r for r, _ in experiences],
        leadership=[r for r, _ in leadership],
        projects=[r for r, _ in projects],
        skills=skills,
        certifications=profile.get("certifications", []),
        target_title=job.title,
        target_company=job.company,
    )

    if use_llm is None:
        use_llm = config.has_llm()
    if use_llm and config.has_llm():
        try:
            _llm_rewrite(resume, job, profile)
        except Exception as exc:
            print(f"  ! LLM bullet rewrite failed ({exc}); keeping original phrasing")
    # Playbook formatting rules applied deterministically to every bullet,
    # LLM-rewritten or verbatim: no trailing period, "&" instead of "and".
    for group in (resume.experience, resume.leadership, resume.projects):
        for role in group:
            role.bullets = [polish_bullet(b) for b in role.bullets]
    return resume


def profile_facts_json(profile: dict) -> str:
    """Serialize the profile's LLM-relevant facts deterministically (sorted keys)
    so the exact same text is sent on every call — required for Anthropic prompt
    caching to hit across runs in a session."""
    import json

    facts = {
        "name": profile.get("personal", {}).get("name"),
        "education": profile.get("education", []),
        "experience": [
            {"role": e.get("role"), "org": e.get("organization"),
             "bullets": [b.get("text") for b in e.get("bullets", [])]}
            for e in profile.get("experience", []) + profile.get("leadership", [])
        ],
        "skills": [s for g in profile.get("skills", []) for s in g.get("skills", [])],
        "certifications": profile.get("certifications", []),
    }
    return json.dumps(facts, indent=2, sort_keys=True, default=str)


def print_llm_usage(label: str, msg) -> None:
    """Surface token usage incl. cache stats so cost isn't invisible."""
    u = getattr(msg, "usage", None)
    if u is None:
        return
    print(f"  · {label} usage: in={getattr(u, 'input_tokens', '?')} "
          f"out={getattr(u, 'output_tokens', '?')} "
          f"cache_write={getattr(u, 'cache_creation_input_tokens', 0) or 0} "
          f"cache_read={getattr(u, 'cache_read_input_tokens', 0) or 0}")


def resume_to_text(r: TailoredResume) -> str:
    """Flatten a tailored resume to plain text (for re-scoring with Phase 2)."""
    parts = [r.name or "", r.contact_line, r.summary or ""]
    for e in r.education:
        parts.append(f"{e.degree or ''} {e.secondary or ''} {e.school or ''} "
                     f"GPA {e.gpa or ''} {e.graduation_date or ''} "
                     + " ".join(e.coursework))
    for group in (r.experience, r.leadership, r.projects):
        for role in group:
            parts.append(f"{role.role or ''} {role.organization or ''} {role.dates or ''}")
            parts.extend(role.bullets)
    parts.append("Skills: " + ", ".join(r.skills))
    parts.extend(r.certifications)
    return "\n".join(p for p in parts if p)


def _llm_rewrite(resume: TailoredResume, job: JobPosting, profile: dict) -> None:
    import json

    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    bullets, index = [], []
    for gname, group in (("experience", resume.experience), ("leadership", resume.leadership),
                         ("projects", resume.projects)):
        for ri, role in enumerate(group):
            for bi, b in enumerate(role.bullets):
                index.append((gname, ri, bi))
                bullets.append(b)
    if not bullets:
        return
    # Static, cacheable block: instructions + the full profile (ground truth the
    # rewrite may not exceed). Identical bytes every run → prompt-cache hits on
    # every generate after the first in a session (~90% off that portion).
    # NOTE: Haiku ignores cache_control below its 2048-token minimum prefix, so
    # with a small profile this block may not cache — harmless (the whole call
    # is ~2k tokens on the cheap model); it engages as the profile grows.
    system = [{
        "type": "text",
        "text": (
            "You rewrite resume bullets to mirror a target job description's "
            "language WITHOUT inventing any facts, numbers, tools, or outcomes "
            "not already present in the bullet or in the candidate profile below. "
            "Keep each bullet to one line, strong action verb first, no pronouns. "
            "Return ONLY a JSON array of the same length and order as the input.\n"
            + RESUME_BULLET_RULES + STYLE_RULES + "\n"
            "CANDIDATE MASTER PROFILE (ground truth — never claim beyond this):\n"
            + profile_facts_json(profile)
        ),
        "cache_control": {"type": "ephemeral"},
    }]
    user = (
        f"TARGET ROLE: {job.title} ({job.role_type}). "
        f"KEY TERMS: {', '.join(job.all_keywords)}\n\n"
        f"BULLETS:\n{json.dumps(bullets, indent=2)}"
    )
    # Mechanical rephrasing → the fast/cheap model; output is ~1 line per bullet,
    # so cap max_tokens near the real output size instead of a blanket 2000.
    msg = client.messages.create(
        model=config.ANTHROPIC_MODEL_FAST,
        max_tokens=min(2000, 150 + 60 * len(bullets)),
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    print_llm_usage(f"bullet rewrite ({config.ANTHROPIC_MODEL_FAST})", msg)
    raw = "".join(b.text for b in msg.content if b.type == "text").strip()
    import re
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw).strip()
    # Tolerate prose before/after the array: decode the first JSON array found.
    start = raw.find("[")
    if start >= 0:
        rewritten, _ = json.JSONDecoder().raw_decode(raw[start:])
    else:
        rewritten = json.loads(raw)
    if len(rewritten) != len(bullets):
        return
    groups = {"experience": resume.experience, "leadership": resume.leadership,
              "projects": resume.projects}
    for (gname, ri, bi), new in zip(index, rewritten):
        if isinstance(new, str) and new.strip():
            groups[gname][ri].bullets[bi] = new.strip()
