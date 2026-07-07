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


def _top_experience(profile: dict, job: JobPosting) -> dict | None:
    exps = profile.get("experience", []) + profile.get("leadership", [])
    return exps[0] if exps else None


def _template(profile: dict, job: JobPosting) -> str:
    personal = profile.get("personal", {})
    name = personal.get("name") or "John Bae"
    company = job.company or "your team"
    title = job.title or "the role"
    edu = (profile.get("education") or [{}])[0]
    grad = edu.get("graduation_date") or "2027"
    major = edu.get("major") or "Accounting and Information Science"

    matched = [k for k in job.required_keywords[:5]]
    skills_phrase = ", ".join(matched[:3]) or "audit, data analysis, and internal controls"

    exp = _top_experience(profile, job)
    exp_line = ""
    if exp:
        org = exp.get("organization", "")
        b = (exp.get("bullets") or [{}])[0].get("text", "")
        exp_line = f" At {org}, I {b[0].lower() + b[1:] if b else 'delivered measurable results'}."

    coursework = ", ".join((edu.get("relevant_coursework") or [])[:3])
    course_line = (f" Coursework in {coursework} backs this up, and I'm on a "
                   "CPA-eligible academic track." if coursework else
                   " I'm on a CPA-eligible academic track.")

    today = date.today().strftime("%B %d, %Y")
    return f"""{today}

Dear {company} Hiring Team,

As {_a(major)} {major} student at the University of Maryland graduating in {grad}, the {title} role at {company} lines up directly with what I've been building toward: work at the intersection of accounting, technology, and analytics.

Your posting emphasizes {skills_phrase}, and my experience maps closely to it.{exp_line} I pair financial rigor with a technical, data-driven approach, and I consistently quantify the impact of my work.

That mix is deliberate.{course_line} It's the combination of technical skills, client service, and compliance judgment that {_a(job.role_type or 'high-impact')} {job.role_type or 'high-impact'} role like this one draws on daily.

Thank you for your time and consideration — I'd welcome the chance to discuss how my background can contribute to your team.

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
