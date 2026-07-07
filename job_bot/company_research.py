"""Company Research Brief (Recommendation #8).

Builds a one-page pre-interview brief for a target company: overview, ATS /
hiring-process intel, "why this firm" angles tuned to John's background, likely
interview topics, the warm contacts already in the network, recent news, and
smart questions to ask.

Three layers, each degrading gracefully:
  1. Curated firm knowledge base (offline, always available) — real hiring
     process + interview-style intel for the firms John targets.
  2. Local context from the SQLite store — open roles, warm connections, and any
     prior decision/rejection history for the company.
  3. Recent news — supplied by the caller (web search / a news MCP / pasted
     headlines) and woven in; or summarized by Claude when a key is present.

Nothing here scrapes the web directly: the runtime/agent feeds `news=[...]` so
the module stays dependency-free and ToS-safe, mirroring the rest of the system.
"""

from __future__ import annotations

from datetime import date

from . import config
from .db import connect
from .skills_ontology import COMPANY_ATS, KNOWN_COMPANIES

# --- Curated firm knowledge base ------------------------------------------------
# Real hiring-process intel for the firms in John's target set. Keys are matched
# case-insensitively against the canonical company name.
FIRM_KB: dict[str, dict] = {
    "Deloitte": {
        "type": "Big 4 — Audit / Risk & Financial Advisory",
        "process": ["Online application (Workday)", "Online assessment / immersive game",
                    "Recruiter / behavioral screen", "Job simulation or case",
                    "Final round / 'Day in the Life'"],
        "values": ["Inclusion", "Integrity", "Outcomes that matter", "Recognition of one another"],
        "topics": ["ITGC / IT general controls", "SOC reports & SOX", "AI risk & governance",
                   "Why Deloitte over the other Big 4", "A time you analyzed messy data"],
        "why_angles": ["Deloitte's investment in AI/Trustworthy-AI risk aligns with my INST "
                       "data-analytics coursework", "Technology Risk sits exactly at the "
                       "accounting + information-science intersection I'm building toward"],
    },
    "PwC": {
        "type": "Big 4 — Assurance / Risk",
        "process": ["Application (Taleo)", "Game-based assessment", "Recruiter screen",
                    "Behavioral + technical round", "Final / partner round"],
        "values": ["Act with integrity", "Make a difference", "Care", "Work together",
                   "Reimagine the possible"],
        "topics": ["Audit methodology", "Digital fitness / data in assurance",
                   "Why PwC", "Teaming & feedback culture"],
        "why_angles": ["PwC's 'digital assurance' push matches my data + controls focus",
                       "The My+ career model rewards the breadth I'm pursuing across "
                       "accounting and information science"],
    },
    "EY": {
        "type": "Big 4 — Assurance / Technology Risk",
        "process": ["Application (Workday)", "EY assessment", "Recruiter screen",
                    "Case / behavioral round", "Final round"],
        "values": ["Integrity", "Respect", "Teaming", "Building a better working world"],
        "topics": ["Technology risk", "Data analytics in audit", "Why EY",
                   "Building a better working world — a concrete example"],
        "why_angles": ["EY's 'better working world' purpose resonates with my mentoring "
                       "and leadership work", "Strong tech-in-audit investment fits my "
                       "INST background"],
    },
    "KPMG": {
        "type": "Big 4 — Audit / Advisory",
        "process": ["Application (Workday)", "Pymetrics-style assessment", "Recruiter screen",
                    "Behavioral round", "Final round"],
        "values": ["Integrity", "Excellence", "Courage", "Together", "For Better"],
        "topics": ["Audit & internal controls", "KPMG Clara / smart-audit tech",
                   "Why KPMG", "Working in diverse teams"],
        "why_angles": ["KPMG Clara's data-driven audit platform fits my analytics interest",
                       "Values-led culture matches how I lead in PSE/IEFS"],
    },
    "Goldman Sachs": {
        "type": "Bulwark / Bulge-bracket investment bank",
        "process": ["Application", "HireVue (recorded) interview", "Superday (multiple rounds)",
                    "Final decision"],
        "values": ["Client service", "Excellence", "Integrity", "Partnership"],
        "topics": ["Why Goldman / why this division", "Markets & current events",
                   "Behavioral fit", "Attention to detail under pressure"],
        "why_angles": ["The analytical rigor of GS operations/risk fits my controls + data "
                       "background", "I want the bar that a bulge-bracket sets early in a career"],
    },
    "Capital One": {
        "type": "Tech-forward bank",
        "process": ["Application", "Online assessment", "Phone screen",
                    "Power Day (case + behavioral)", "Final"],
        "values": ["Excellence", "Do the right thing"],
        "topics": ["Case interview (business/analytics)", "Why Capital One",
                   "Data-driven decision making", "A time you used data to drive a decision"],
        "why_angles": ["Capital One's data-first, tech-forward banking model is exactly the "
                       "accounting + information-science blend I'm building", "Their case style "
                       "rewards structured analytical thinking I practice in coursework"],
    },
}

# Generic fallback so any company still produces a usable brief.
GENERIC = {
    "type": "Target employer",
    "process": ["Application", "Recruiter / phone screen", "Behavioral + technical round",
                "Final round"],
    "values": ["Integrity", "Teamwork", "Excellence"],
    "topics": ["Why this company", "A behavioral story (STAR)", "Role-specific technical fit"],
    "why_angles": ["My accounting + information-science background fits roles at the "
                   "controls/data intersection"],
}


def _canonical(company: str) -> str:
    """Map a free-text company to its canonical display name when known."""
    low = company.strip().lower()
    for key, disp in KNOWN_COMPANIES.items():
        if key in low or low in key:
            return disp
    return company.strip()


def _kb(company: str) -> dict:
    canon = _canonical(company)
    for name, data in FIRM_KB.items():
        if name.lower() == canon.lower():
            return data
    return GENERIC


def _local_context(con, company: str) -> dict:
    low = f"%{company.lower()}%"
    jobs = list(con.execute(
        "SELECT title, location, market_tier, ats_score, status, url FROM jobs "
        "WHERE lower(company) LIKE ? ORDER BY priority DESC LIMIT 5", (low,)))
    conns = list(con.execute(
        "SELECT name, title, relationship, warmth FROM connections "
        "WHERE lower(company) LIKE ? ORDER BY warmth DESC LIMIT 8", (low,)))
    decisions = list(con.execute(
        "SELECT verdict, ats_score, created_at FROM decisions "
        "WHERE lower(company) LIKE ? ORDER BY created_at DESC LIMIT 3", (low,)))
    rejections = list(con.execute(
        "SELECT stage, role_title, rejected_on FROM rejections "
        "WHERE lower(company) LIKE ? ORDER BY created_at DESC LIMIT 3", (low,)))
    return {
        "jobs": [dict(r) for r in jobs],
        "connections": [dict(r) for r in conns],
        "decisions": [dict(r) for r in decisions],
        "rejections": [dict(r) for r in rejections],
    }


def _ats_platform(company: str) -> str | None:
    low = _canonical(company).lower()
    for key, plat in COMPANY_ATS.items():
        if key in low or low in key:
            return plat
    return None


def smart_questions(kb: dict, role: str) -> list[str]:
    """Thoughtful questions for the candidate to ask, tuned to firm + role."""
    qs = [
        f"What does success look like in the first 6–12 months in this {role} role?",
        "How is the team using data/analytics and AI in its day-to-day work right now?",
        "What's the biggest change the group is navigating this year?",
    ]
    if "Big 4" in kb.get("type", ""):
        qs.append("How does the firm support someone pursuing the CPA while ramping up?")
    if "bank" in kb.get("type", "").lower() or "Bulge" in kb.get("type", ""):
        qs.append("How does the team balance speed with control/risk in its work?")
    return qs


def build_brief(company: str, role: str = "this role", *,
                news: list[str] | None = None, use_llm: bool | None = None) -> dict:
    """Assemble a structured company research brief.

    `news` is an optional list of recent headline strings (fed by web search /
    an MCP). When a key is present and `use_llm` isn't False, Claude turns the
    raw context + news into a tighter narrative.
    """
    canon = _canonical(company)
    kb = _kb(company)
    con = connect()
    try:
        ctx = _local_context(con, canon)
    finally:
        con.close()

    brief = {
        "company": canon,
        "role": role,
        "generated_on": date.today().isoformat(),
        "type": kb["type"],
        "ats_platform": _ats_platform(canon),
        "hiring_process": kb["process"],
        "values": kb["values"],
        "likely_topics": kb["topics"],
        "why_this_firm": kb["why_angles"],
        "smart_questions": smart_questions(kb, role),
        "warm_contacts": ctx["connections"],
        "open_roles": ctx["jobs"],
        "prior_decisions": ctx["decisions"],
        "prior_rejections": ctx["rejections"],
        "recent_news": news or [],
    }

    if use_llm is None:
        use_llm = config.has_llm()
    if use_llm and config.has_llm():
        try:
            brief["narrative"] = _llm_narrative(brief)
        except Exception as exc:  # pragma: no cover
            print(f"  ! LLM brief narrative failed ({exc}); using structured brief only")
    return brief


def _llm_narrative(brief: dict) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    news = "\n".join(f"- {n}" for n in brief["recent_news"]) or "(none provided)"
    prompt = (
        f"You are prepping John Bae (UMD Accounting + Information Science) for an interview "
        f"for the {brief['role']} role at {brief['company']} ({brief['type']}).\n"
        f"Firm values: {', '.join(brief['values'])}.\n"
        f"Likely topics: {', '.join(brief['likely_topics'])}.\n"
        f"Recent news headlines:\n{news}\n\n"
        "Write a tight 150-word pre-interview brief: what the firm is focused on right now, "
        "how John should frame his 'why this firm', and one concrete talking point that "
        "connects recent news to the role. Use only the facts given; do not invent specifics."
    )
    msg = client.messages.create(model=config.ANTHROPIC_MODEL, max_tokens=400,
                                 messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in msg.content if b.type == "text").strip()


def format_brief(b: dict) -> str:
    """Render the brief as readable plain text for the CLI."""
    lines = [
        f"\n{'='*64}",
        f"COMPANY RESEARCH BRIEF — {b['company']}",
        f"{b['role']}  ·  {b['type']}  ·  generated {b['generated_on']}",
        f"{'='*64}",
    ]
    if b.get("ats_platform"):
        lines.append(f"\nATS platform: {b['ats_platform']}  (tailor the resume to this)")

    lines.append("\nHIRING PROCESS")
    for i, step in enumerate(b["hiring_process"], 1):
        lines.append(f"  {i}. {step}")

    lines.append("\nFIRM VALUES (mirror these in your stories)")
    lines.append("  " + " · ".join(b["values"]))

    lines.append("\nWHY THIS FIRM — angles for you")
    for a in b["why_this_firm"]:
        lines.append(f"  • {a}")

    lines.append("\nLIKELY INTERVIEW TOPICS")
    for t in b["likely_topics"]:
        lines.append(f"  • {t}")

    if b["recent_news"]:
        lines.append("\nRECENT NEWS (work one into 'why this firm')")
        for n in b["recent_news"]:
            lines.append(f"  • {n}")

    if b["warm_contacts"]:
        lines.append("\nWARM CONTACTS HERE (reach out before/after)")
        for c in b["warm_contacts"]:
            tag = f" [{c['relationship']}]" if c.get("relationship") else ""
            title = f" — {c['title']}" if c.get("title") else ""
            lines.append(f"  • {c['name']}{title}{tag}  (warmth {c.get('warmth','?')})")
    else:
        lines.append("\nWARM CONTACTS HERE: none on file — consider a cold UMD/PSE outreach.")

    if b["open_roles"]:
        lines.append("\nOPEN ROLES ON FILE")
        for j in b["open_roles"]:
            ats = f"  ATS {j['ats_score']:.0f}" if j.get("ats_score") is not None else ""
            lines.append(f"  • {j['title']}  ({j.get('location','?')}){ats}  [{j.get('status','')}]")

    if b["prior_rejections"]:
        lines.append("\n⚠ PRIOR HISTORY HERE")
        for r in b["prior_rejections"]:
            lines.append(f"  • rejected at {r['stage']} ({r.get('role_title') or '—'})")

    lines.append("\nSMART QUESTIONS TO ASK THEM")
    for q in b["smart_questions"]:
        lines.append(f"  • {q}")

    if b.get("narrative"):
        lines.append("\nBRIEF (AI-written)")
        lines.append("  " + b["narrative"].replace("\n", "\n  "))

    lines.append(f"\n{'='*64}\n")
    return "\n".join(lines)
