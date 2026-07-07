"""Post-interview thank-you email generator.

Drafts a short, specific thank-you for each interviewer, referencing what was
discussed. Template-based by default; Claude-drafted when a key is present.
"""

from __future__ import annotations

from . import config


def generate_thankyou(profile: dict, company: str, role: str,
                      interviewer: str | None = None, topics: list[str] | None = None,
                      use_llm: bool | None = None) -> str:
    if use_llm is None:
        use_llm = config.has_llm()
    if use_llm and config.has_llm():
        try:
            return _llm_thankyou(profile, company, role, interviewer, topics)
        except Exception as exc:
            print(f"  ! LLM thank-you failed ({exc}); using template")
    return _template(profile, company, role, interviewer, topics)


def _template(profile: dict, company: str, role: str,
              interviewer: str | None, topics: list[str] | None) -> str:
    name = profile.get("personal", {}).get("name", "John Bae")
    first = name.split()[0]
    who = interviewer.split()[0] if interviewer else "team"
    greeting = f"Hi {interviewer.split()[0]}," if interviewer else f"Hi {company} team,"
    topic = (topics or ["the team's work"])[0]
    return f"""Subject: Thank you — {role}

{greeting}

Thank you for taking the time to speak with me today about the {role} role at {company}. I really enjoyed our conversation, especially discussing {topic} — it reinforced my excitement about the opportunity and the team.

Our discussion confirmed that my background in audit, data analysis, and internal controls lines up well with what you're looking for, and I'm confident I could contribute quickly. Please don't hesitate to reach out if there's anything else I can provide.

Thanks again for your time and consideration — I look forward to the next steps.

Best,
{name}
{profile.get('personal', {}).get('email', '')}"""


def _llm_thankyou(profile: dict, company: str, role: str,
                  interviewer: str | None, topics: list[str] | None) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    name = profile.get("personal", {}).get("name", "John Bae")
    prompt = (
        f"Write a concise, genuine post-interview thank-you email from {name} to "
        f"{interviewer or 'the interview team'} for the {role} role at {company}. "
        f"Reference these discussion points specifically: {', '.join(topics or [])}. "
        "Under 130 words, warm but professional, no clichés. Include a Subject line. "
        "Use only real facts; do not invent details."
    )
    msg = client.messages.create(model=config.ANTHROPIC_MODEL, max_tokens=400,
                                 messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in msg.content if b.type == "text").strip()
