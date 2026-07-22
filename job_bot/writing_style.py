"""Shared writing guardrails for every LLM-generated text surface (resume
bullets, cover letters, LinkedIn About, outreach messages).

Two sources of truth, merged here so they can't drift per-prompt:
- Anti-cliché rules (STYLE_RULES / BANNED_PHRASES).
- ``docs/resume_branding_playbook.md`` — the bullet
  formula, length bands, formatting rules, preferred vocabulary, cover-letter
  structure, company-values mirroring, and outreach conventions. Edit the
  playbook first, then mirror changes here.

NOTE: the playbook lists "Leveraged" as a preferred verb, but it's on the
banned-cliché list; the ban wins, so it's deliberately absent below.
"""

from __future__ import annotations

import re

BANNED_PHRASES = [
    "leverage", "leveraging", "spearhead", "spearheaded", "utilize", "utilized",
    "robust", "dynamic", "results-driven", "detail-oriented", "team player",
    "passionate about", "seamless", "seamlessly", "synergy", "synergies",
    "furthermore", "moreover", "in today's fast-paced", "ever-evolving",
    "cutting-edge", "game-changer", "delve into", "unlock", "unlocking",
    "empower", "empowering", "holistic", "streamline", "streamlined",
]

STYLE_RULES = f"""
Writing style rules — this text will be read by a human, not graded on buzzword density:
- Never use these words/phrases: {", ".join(BANNED_PHRASES)}.
- Vary sentence length and structure — don't start consecutive lines/bullets with
  the same verb or pattern.
- Every claim should carry one concrete, specific detail (a number, a tool name,
  a scope) rather than a generic quality claim like "strong communication skills."
- Write the way a sharp, slightly understated person would describe their own
  work to a peer — not the way a corporate brochure would describe it.
- No throat-clearing openers ("I am excited to..."), no generic closers
  ("I look forward to hearing from you") unless they carry a specific reason why.
"""

# --- Resume bullets (playbook: bullet formula, length bands, formatting) ----

PREFERRED_VERBS = [
    "Managed", "Conducted", "Analyzed", "Led", "Prepared", "Reviewed",
    "Developed", "Strengthened", "Implemented", "Optimized", "Coordinated",
    "Evaluated",
]

WEAK_VERBS = ["Helped", "Worked on", "Responsible for", "Assisted"]

BUSINESS_LANGUAGE = [
    "internal controls", "regulatory compliance", "audit readiness",
    "documentation accuracy", "quality assurance", "stakeholder communication",
    "data validation", "financial reporting", "analytical reasoning",
    "variance analysis", "process improvement", "client service",
    "governance", "risk assessment",
]

RESUME_BULLET_RULES = f"""
Resume bullet rules (the John Bae standard):
- Structure: action verb -> what you did -> how you did it -> business impact.
  A strong bullet answers at least three of: what did you do, how did you do it,
  why did it matter, can it be quantified.
- Open with a verb like {", ".join(PREFERRED_VERBS)} when it fits the fact.
  Never open with {", ".join(WEAK_VERBS)}.
- Where the underlying fact supports it, phrase impact in this vocabulary:
  {", ".join(BUSINESS_LANGUAGE)}.
- Keep each bullet either short (85-95 characters) or long (170-190 characters),
  not in between.
- Formatting: no period at the end of a bullet, write "&" instead of "and",
  keep verb tense consistent. Plain text only — no markdown; metrics are bolded
  automatically when the resume is rendered.
- Never rewrite more than needed: change only wording that improves alignment
  with the target JD (roughly 10-20% of a bullet); a bullet that already fits
  should come back unchanged.
"""

# --- Cover letters (playbook: 4-paragraph structure, company mirroring) -----

COVER_LETTER_STRUCTURE = """
Cover letter structure — exactly 4 short paragraphs:
1. Who the candidate is, why this company, and one specific reason for the interest.
2. Strongest relevant highlights: audit/tax work, leadership, analytics, client
   service, technology.
3. Coursework, CPA eligibility, and how the experience fits this specific role.
4. A short, appreciative closing.
Subtly mirror the company's public values in the candidate's own words; never
copy slogans directly.
"""

COMPANY_VALUES = {
    "kpmg": "integrity, innovation, quality, future-forward thinking, client service",
    "deloitte": "impact, leadership, trust, innovation",
    "pwc": "trust, solving important problems, technology, collaboration",
    "ey": "building a better working world, transformation, analytics",
}


def company_values_hint(company: str | None) -> str:
    """One-line hint naming the target firm's public values, when known."""
    if not company:
        return ""
    low = company.lower()
    for key, values in COMPANY_VALUES.items():
        if re.search(rf"\b{key}\b", low):
            return (f"{company}'s public values (echo in your own words, never "
                    f"quote slogans): {values}.")
    return ""


# --- Outreach messages (playbook: recruiter + networking email rules) -------

OUTREACH_RULES = """
Outreach message rules:
- Recruiter emails: 5-8 sentences — greeting, one brief warm line, the purpose,
  continued interest in the role, thanks, signature.
- Networking messages: under 150 words; thank them, reference the shared
  background or previous interaction, explain why you're reaching out, and never
  ask directly for a job — ask about opportunities or next steps instead.
"""

# --- Deterministic bullet formatting (playbook: formatting rules) -----------

# Metric tokens to bold at render time: $380K, 800+, 20%, 3.5, 100+ ...
METRIC_RE = re.compile(r"\$?\d[\d,]*(?:\.\d+)?\s?[KMB]?\+?%?")


def split_metrics(text: str) -> list[tuple[str, bool]]:
    """Split text into (chunk, is_metric) pairs so renderers can bold metrics."""
    out, pos = [], 0
    for m in METRIC_RE.finditer(text):
        if m.start() > pos:
            out.append((text[pos:m.start()], False))
        out.append((m.group(), True))
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], False))
    return out or [(text, False)]


def polish_bullet(text: str) -> str:
    """Enforce the playbook's mechanical bullet formatting on any bullet,
    LLM-rewritten or verbatim: collapse whitespace, no trailing period,
    "&" instead of "and"."""
    t = " ".join(text.split()).rstrip(".")
    return re.sub(r"\band\b", "&", t)
