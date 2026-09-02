"""Cover letter generator: mirrors JD language using only real profile facts.

Claude-drafted when an API key is present; otherwise a clean template fills in
the candidate's strongest matching experience and the JD's key terms.
"""

from __future__ import annotations

from datetime import date

from . import config
from .jd_models import JobPosting
from .writing_style import COVER_LETTER_STRUCTURE, STYLE_RULES, company_values_hint


def _a(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def _serial(items: list[str]) -> str:
    """Oxford-comma join. Without this the template ran its keyword list
    straight into the following clause -- "emphasizes accounting, attention to
    detail, auditing, and my experience maps closely to it" reads as a
    four-item list with a broken last element."""
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def _first_person(bullet: str) -> str:
    """Re-conjugate a resume bullet for use in letter prose.

    Resume bullets are subjectless and third-person singular by convention
    ("Builds & ships full-stack features..."). Dropping one into a sentence
    that starts "At CowSync, I ..." produced "I builds & ships" -- a
    subject-verb break in the letter's most important sentence. Past-tense
    bullets are already correct; only the present-tense -s form needs undoing.
    """
    def base(verb: str) -> str:
        low = verb.lower()
        if low.endswith("ed") or not low.endswith("s") or low.endswith("ss"):
            return low                  # past tense, or not an -s form
        if low.endswith("ies") and len(low) > 4:
            return low[:-3] + "y"       # identifies -> identify
        if low.endswith(("ches", "shes", "sses", "xes", "zes")):
            return low[:-2]             # pitches -> pitch, fixes -> fix
        return low[:-1]                 # builds -> build, uses -> use

    words = (bullet or "").split()
    if not words:
        return ""
    out = [base(words[0])]
    i = 1
    # Compound openers ("Builds & ships ...") need every verb conjugated, not
    # just the first, or the letter reads "I build & ships".
    while i + 1 < len(words) and words[i] in ("&", "and"):
        out += [words[i], base(words[i + 1])]
        i += 2
    return " ".join(out + words[i:])


def _top_experience(profile: dict, job: JobPosting) -> tuple[dict, str] | None:
    """The single most JD-relevant (role, bullet) pair, not simply the first
    one on file -- the newest job is not always the one that argues for you."""
    from .tailor import _bullet_relevance, _jd_aliases

    aliases = _jd_aliases(job)
    jd_text = job.raw_text or ""
    best = None
    for entry in profile.get("experience", []) + profile.get("leadership", []):
        for b in entry.get("bullets", []):
            text = b.get("text") if isinstance(b, dict) else str(b)
            if not text:
                continue
            rel = _bullet_relevance(b if isinstance(b, dict) else {"text": text},
                                    aliases, jd_text)
            if best is None or rel > best[0]:
                best = (rel, entry, text)
    return (best[1], best[2]) if best else None


def _supported_keywords(profile: dict, job: JobPosting) -> list[str]:
    """JD keywords the candidate can actually back up.

    The template used to name `job.required_keywords[:3]`, which is sorted
    alphabetically — so an IT Risk letter opened with "Your posting emphasizes
    access management ... and that is where my experience sits" for a candidate
    with no access-management experience. Naming a requirement you do not meet,
    in the sentence claiming you meet it, is the one thing a cover letter must
    never do."""
    from .ats_engine import load_profile, profile_text  # noqa: F401
    from .similarity import contains_phrase
    from .skills_ontology import SKILL_ALIASES

    try:
        corpus = profile_text(profile).lower()
    except Exception:
        return list(job.required_keywords[:3])
    out = []
    for kw in list(job.required_keywords) + list(job.preferred_keywords):
        if any(contains_phrase(corpus, a) for a in SKILL_ALIASES.get(kw, [kw])):
            out.append(kw)
    return out


def _template(profile: dict, job: JobPosting) -> str:
    personal = profile.get("personal", {})
    name = personal.get("name") or "John Bae"
    company = job.company or "your team"
    title = job.title or "the role"
    edu = (profile.get("education") or [{}])[0]
    grad = edu.get("graduation_date") or "2027"
    major = edu.get("major") or "Accounting and Information Science"

    skills_phrase = (_serial(_supported_keywords(profile, job)[:3])
                     or "audit, data analysis, and internal controls")

    top = _top_experience(profile, job)
    exp_line = ""
    if top:
        entry, bullet = top
        org = entry.get("organization", "")
        # Resume bullets use "&" by house style; letter prose should not.
        phrase = _first_person(bullet).rstrip(".").replace(" & ", " and ")
        exp_line = f" At {org}, I {phrase}." if phrase else ""

    # Rank by JD relevance, exactly as the resume does — reading the profile
    # order gave an IT-audit letter "Discovering New Ventures" while
    # Intermediate Accounting sat unused two lines further down.
    from .tailor import _jd_aliases, _rank_by_jd
    coursework = _serial(_rank_by_jd(edu.get("relevant_coursework") or [],
                                     job, _jd_aliases(job))[:3])

    # job.role_type is a taxonomy label ("Audit / Assurance"); a spaced slash
    # mid-sentence reads as machine residue. Say it the way a person would.
    role_phrase = (job.role_type or "").replace(" / ", " and ").lower() or "role"
    course_line = (f" I chose coursework in {coursework}, and I am on a "
                   "CPA-eligible academic track." if coursework else
                   " I am on a CPA-eligible academic track.")

    # "%d" zero-pads ("September 01, 2026"); letters are dated the way people
    # write dates.
    today = f"{date.today():%B} {date.today().day}, {date.today():%Y}"
    return f"""{today}

Dear {company} Hiring Team,

I am {_a(major)} {major} student at the University of Maryland, graduating in {grad}, and I am applying for the {title} role at {company}. It lines up directly with what I have been building toward: work at the intersection of accounting, technology, and analytics.

Your posting emphasizes {skills_phrase}, and that is where my experience sits.{exp_line} I pair financial rigor with a technical, data-driven approach, and I quantify the impact of my work.

That mix is deliberate:{course_line} The combination of technical skill, client service, and compliance judgment is what {_a(role_phrase)} {role_phrase} role like this one draws on daily.

Thank you for your time and consideration — I would welcome the chance to discuss how my background can contribute to your team.

Sincerely,
{name}
{personal.get('email') or ''}  |  {personal.get('phone') or ''}
"""


def generate_cover_letter(profile: dict, job: JobPosting, use_llm: bool | None = None) -> str:
    if use_llm is None:
        use_llm = config.has_llm()
    if use_llm and config.has_llm():
        try:
            return _llm_cover_letter(profile, job)
        except Exception as exc:
            print(f"  ! LLM cover letter failed ({exc}); using template")
    return _template(profile, job)


def _llm_cover_letter(profile: dict, job: JobPosting) -> str:
    import anthropic

    from .tailor import print_llm_usage, profile_facts_json

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    # Static, cacheable block: instructions + profile facts (identical bytes every
    # run — see profile_facts_json). The per-job part stays in the user message.
    system = [{
        "type": "text",
        "text": (
            "You write concise, professional one-page cover letters. Mirror the "
            "target job description's language but use ONLY the candidate facts "
            "below — never invent experience, employers, metrics, or skills. "
            "Warm but professional; no clichés like 'I am writing to express'.\n"
            + COVER_LETTER_STRUCTURE + STYLE_RULES + "\n"
            "CANDIDATE FACTS (JSON):\n" + profile_facts_json(profile)
        ),
        "cache_control": {"type": "ephemeral"},
    }]
    values = company_values_hint(job.company)
    user = (f"JOB: {job.title} at {job.company}. Role type: {job.role_type}. "
            f"Key terms: {', '.join(job.all_keywords)}"
            + (f"\n{values}" if values else ""))
    # Judgment-heavy call → keep the full model (config.ANTHROPIC_MODEL).
    msg = client.messages.create(model=config.ANTHROPIC_MODEL, max_tokens=1200,
                                 system=system,
                                 messages=[{"role": "user", "content": user}])
    print_llm_usage(f"cover letter ({config.ANTHROPIC_MODEL})", msg)
    return "".join(b.text for b in msg.content if b.type == "text").strip()


def cover_letter_to_docx(text: str, out_path):
    import docx
    from docx.shared import Pt

    doc = docx.Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    for para in text.split("\n"):
        p = doc.add_paragraph(para)
        p.paragraph_format.space_after = Pt(6)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    return out_path
