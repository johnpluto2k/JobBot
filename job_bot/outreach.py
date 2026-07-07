"""Phase 6: personalized outreach message drafting.

Generates short, specific referral requests / networking intros / follow-ups
that reference shared background (UMD, Pi Sigma Epsilon, IEFS, TerpTax) and the
exact role — not generic templates. Claude-drafted when a key is present.
"""

from __future__ import annotations

from . import config
from .decision_models import ConnectionMatch
from .writing_style import OUTREACH_RULES, STYLE_RULES

AFFILIATION_PHRASE: dict[str, str] = {
    "pse": "as a fellow Pi Sigma Epsilon member",
    "umd": "as a fellow Terp",
    "iefs": "through our shared IEFS background",
    "terptax": "through TerpTax",
    "recruiter": "",
    "first_degree": "",
    "second_degree": "",
    "alum": "as a fellow University of Maryland student",
}

PITCH = ("I'm a UMD Accounting + Information Science student (graduating 2027) focused on "
         "audit, technology risk, and data analytics.")


def _shared(rel: str) -> str:
    return AFFILIATION_PHRASE.get(rel, "")


def referral_request(contact: ConnectionMatch, company: str, role_title: str,
                     candidate: str = "John") -> str:
    shared = _shared(contact.relationship)
    opener = f"Hi {(contact.name or 'there').split()[0]},"
    intro = (f"I hope you're doing well{(' — reaching out ' + shared) if shared else ''}. "
             f"{PITCH}")
    if contact.relationship == "recruiter":
        body = (f"I'm very interested in the {role_title} role at {company} and wanted to introduce "
                "myself directly. I've attached a resume tailored to the posting — would you be open "
                "to a quick chat about the team and process?")
    else:
        body = (f"I saw {company} has an opening for {role_title}, which lines up closely with my "
                f"background. Since you're on the inside as {contact.title or 'a team member'}, would "
                "you be willing to refer me or share any advice on putting my application forward?")
    close = "Either way, I appreciate your time. Thanks so much!\n\nBest,\n" + candidate
    return f"{opener}\n\n{intro}\n\n{body}\n\n{close}"


def networking_intro(contact: ConnectionMatch, company: str, candidate: str = "John") -> str:
    shared = _shared(contact.relationship) or "as a fellow UMD student"
    opener = f"Hi {(contact.name or 'there').split()[0]},"
    body = (f"I came across your profile {shared} and would love to connect. {PITCH} "
            f"I'm exploring opportunities at {company} and would really value 15 minutes to hear "
            f"about your path and what your team looks for. No pressure at all — thanks for considering!")
    return f"{opener}\n\n{body}\n\nBest,\n{candidate}"


def follow_up(contact: ConnectionMatch, company: str, role_title: str,
              candidate: str = "John") -> str:
    opener = f"Hi {(contact.name or 'there').split()[0]},"
    body = (f"Just following up on my note about the {role_title} role at {company} — I know things "
            "get busy. I remain very interested and am happy to make it easy with anything you need "
            "from me. Thanks again for your time!")
    return f"{opener}\n\n{body}\n\nBest,\n{candidate}"


def draft(kind: str, contact: ConnectionMatch, company: str, role_title: str,
          candidate: str = "John", use_llm: bool | None = None) -> str:
    if use_llm is None:
        use_llm = config.has_llm()
    if use_llm and config.has_llm():
        try:
            return _llm_draft(kind, contact, company, role_title, candidate)
        except Exception as exc:
            print(f"  ! LLM outreach draft failed ({exc}); using template")
    if kind == "intro":
        return networking_intro(contact, company, candidate)
    if kind == "follow_up":
        return follow_up(contact, company, role_title, candidate)
    return referral_request(contact, company, role_title, candidate)


def _llm_draft(kind: str, contact: ConnectionMatch, company: str, role_title: str,
               candidate: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    prompt = (
        f"Write a short, specific, warm LinkedIn message ({kind.replace('_',' ')}) from {candidate}, "
        f"a UMD Accounting + Information Science student (grad 2027, focus: audit/tech risk/analytics), "
        f"to {contact.name} ({contact.title} at {company}). Relationship: {contact.relationship}. "
        f"Target role: {role_title}. No clichés, reference the shared background "
        "naturally, end with a low-pressure ask. Return only the message.\n"
        + OUTREACH_RULES + STYLE_RULES
    )
    msg = client.messages.create(model=config.ANTHROPIC_MODEL, max_tokens=400,
                                 messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in msg.content if b.type == "text").strip()
