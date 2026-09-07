"""Phase 6: personalized outreach message drafting.

Generates short, specific referral requests / networking intros / follow-ups
that reference shared background (school, student orgs, past programs) and the
exact role — not generic templates. Claude-drafted when a key is present.

The shared-background phrases come from the ``Relationship`` tag on each imported
connection. Generic tags are built in; add your own (a fraternity, a fellowship,
a volunteer program) in ``data/affiliations.json`` as ``{"tag": "phrase"}`` and
they are merged over the defaults.
"""

from __future__ import annotations

import json

from . import candidate, config
from .decision_models import ConnectionMatch
from .writing_style import OUTREACH_RULES, STYLE_RULES

_DEFAULT_AFFILIATIONS: dict[str, str] = {
    "recruiter": "",
    "first_degree": "",
    "second_degree": "",
    "alum": "as a fellow alum",
    "school": "as a fellow student",
}


def affiliation_phrases() -> dict[str, str]:
    """Relationship tag -> "as a fellow ..." phrase, with the user's own tags merged in."""
    phrases = dict(_DEFAULT_AFFILIATIONS)
    school = candidate.school()
    if school:
        phrases["alum"] = f"as a fellow {school} alum"
        phrases["school"] = f"as a fellow {school} student"
    try:
        extra = json.loads((config.OUTPUT_DIR / "affiliations.json").read_text(encoding="utf-8"))
        if isinstance(extra, dict):
            phrases.update({str(k): str(v) for k, v in extra.items()})
    except (OSError, ValueError):
        pass
    return phrases


def pitch() -> str:
    """One-sentence self-introduction built from the profile."""
    who = candidate.blurb()
    focus = candidate.focus()
    return f"I'm {who}" + (f" focused on {focus}." if focus else ".")


def _first_name() -> str:
    return candidate.first_name()


def _candidate_blurb() -> str:
    focus = candidate.focus()
    return candidate.blurb() + (f" (focus: {focus})" if focus else "")


def _shared(rel: str) -> str:
    return affiliation_phrases().get(rel, "")


def referral_request(contact: ConnectionMatch, company: str, role_title: str,
                     candidate: str | None = None) -> str:
    candidate = candidate or _first_name()
    shared = _shared(contact.relationship)
    opener = f"Hi {(contact.name or 'there').split()[0]},"
    intro = (f"I hope you're doing well{(' — reaching out ' + shared) if shared else ''}. "
             f"{pitch()}")
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


def networking_intro(contact: ConnectionMatch, company: str, candidate: str | None = None) -> str:
    candidate = candidate or _first_name()
    shared = _shared(contact.relationship) or affiliation_phrases()["school"]
    opener = f"Hi {(contact.name or 'there').split()[0]},"
    body = (f"I came across your profile {shared} and would love to connect. {pitch()} "
            f"I'm exploring opportunities at {company} and would really value 15 minutes to hear "
            f"about your path and what your team looks for. No pressure at all — thanks for considering!")
    return f"{opener}\n\n{body}\n\nBest,\n{candidate}"


def follow_up(contact: ConnectionMatch, company: str, role_title: str,
              candidate: str | None = None) -> str:
    candidate = candidate or _first_name()
    opener = f"Hi {(contact.name or 'there').split()[0]},"
    body = (f"Just following up on my note about the {role_title} role at {company} — I know things "
            "get busy. I remain very interested and am happy to make it easy with anything you need "
            "from me. Thanks again for your time!")
    return f"{opener}\n\n{body}\n\nBest,\n{candidate}"


def draft(kind: str, contact: ConnectionMatch, company: str, role_title: str,
          candidate: str | None = None, use_llm: bool | None = None) -> str:
    candidate = candidate or _first_name()
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
        f"{_candidate_blurb()}, "
        f"to {contact.name} ({contact.title} at {company}). Relationship: {contact.relationship}. "
        f"Target role: {role_title}. No clichés, reference the shared background "
        "naturally, end with a low-pressure ask. Return only the message.\n"
        + OUTREACH_RULES + STYLE_RULES
    )
    msg = client.messages.create(model=config.ANTHROPIC_MODEL, max_tokens=400,
                                 messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in msg.content if b.type == "text").strip()
