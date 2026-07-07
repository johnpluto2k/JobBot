"""Phase 7: build a STAR+ story bank from the master profile.

Extracts the strongest stories from real experience, maps each to the
competencies it demonstrates, and drafts STAR+ structure (Situation, Task,
Action, Result, +Reflection, +Connection). Claude fills the softer
Reflection/Connection lines when a key is present; otherwise prompts are left
for the candidate to complete.
"""

from __future__ import annotations

import re

from . import config
from .interview_models import Story

# competency inference from text
COMPETENCY_SIGNALS: dict[str, list[str]] = {
    "Leadership": ["led", "managed", "supervised", "mentor", "trained", "directed", "oversaw"],
    "Ownership / Initiative": ["built", "designed", "launched", "created", "initiated", "implemented"],
    "Analytical / Problem Solving": ["analyzed", "identified", "evaluated", "diagnosed", "data",
                                     "reduced", "improved"],
    "Financial Acumen": ["budget", "financial", "cost", "savings", "revenue", "audit", "expense"],
    "Communication / Stakeholders": ["client", "stakeholder", "presented", "communicated",
                                     "satisfaction", "service"],
    "Teamwork / Collaboration": ["collaborated", "cross-functional", "team", "partnered", "committee"],
    "Attention to Detail / Compliance": ["compliance", "accuracy", "controls", "regulatory",
                                         "documentation", "quality"],
    "Technical / Building": ["python", "sql", "javascript", "api", "database", "app", "automation"],
}


def _competencies(text: str) -> list[str]:
    low = text.lower()
    hits = [c for c, sig in COMPETENCY_SIGNALS.items() if any(w in low for w in sig)]
    return hits[:4] or ["Ownership / Initiative"]


def _strength(entry: dict) -> float:
    bullets = entry.get("bullets", [])
    if not bullets:
        return 0.0
    quant = sum(1 for b in bullets if b.get("quantified"))
    avg = sum(b.get("strength_score", 0.5) for b in bullets) / len(bullets)
    return 0.6 * avg + 0.4 * (quant / len(bullets))


def _quant_bullet(bullets: list[dict]) -> str:
    for b in bullets:
        if b.get("quantified"):
            return b.get("text", "")
    return bullets[0].get("text", "") if bullets else ""


def _story_from(entry: dict, kind: str) -> Story:
    org = entry.get("organization") or entry.get("name") or ""
    role = entry.get("role") or ""
    bullets = entry.get("bullets", [])
    texts = [b.get("text", "") for b in bullets]
    joined = " ".join(texts)
    result_b = _quant_bullet(bullets)

    title = f"{role} — {org}".strip(" —") or (entry.get("name") or "Story")
    return Story(
        title=title,
        source=f"{kind}: {org}",
        competencies=_competencies(joined + " " + role),
        situation=f"As {role or 'a team member'} at {org}, "
                  "I was responsible for the work below.",
        task=(texts and f"Key responsibility: {_first_clause(texts[0])}") or "",
        action=" ".join(texts[:2]),
        result=result_b,
        reflection="",   # filled by LLM or candidate
        connection="",
        quantified=any(b.get("quantified") for b in bullets),
    )


def _first_clause(text: str) -> str:
    return re.split(r"[,.;]", text)[0].strip()


def build_story_bank(profile: dict, top_n: int = 10, use_llm: bool | None = None) -> list[Story]:
    candidates: list[tuple[float, dict, str]] = []
    for e in profile.get("experience", []):
        candidates.append((_strength(e), e, "Experience"))
    for l in profile.get("leadership", []):
        candidates.append((_strength(l), l, "Leadership"))
    for p in profile.get("projects", []):
        candidates.append((_strength(p) + 0.1, p, "Project"))  # projects show initiative

    candidates.sort(key=lambda x: x[0], reverse=True)
    stories = [_story_from(e, kind) for _, e, kind in candidates[:top_n]]

    if use_llm is None:
        use_llm = config.has_llm()
    if use_llm and config.has_llm():
        try:
            _llm_polish(stories, profile)
        except Exception as exc:
            print(f"  ! LLM story polish failed ({exc}); reflection/connection left blank")
    return stories


def _llm_polish(stories: list[Story], profile: dict) -> None:
    import json

    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    target = ", ".join(profile.get("targets", {}).get("target_roles", []))
    payload = [{"title": s.title, "action": s.action, "result": s.result} for s in stories]
    prompt = (
        "For each story, write two one-sentence fields using ONLY the facts given: "
        "'reflection' (what the candidate learned) and 'connection' (how it maps to target roles: "
        f"{target}). Return a JSON array of objects with keys title, reflection, connection.\n\n"
        f"{json.dumps(payload, indent=2)}"
    )
    msg = client.messages.create(model=config.ANTHROPIC_MODEL, max_tokens=1500,
                                 messages=[{"role": "user", "content": prompt}])
    raw = "".join(b.text for b in msg.content if b.type == "text").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw).strip()
    by_title = {o.get("title"): o for o in json.loads(raw)}
    for s in stories:
        o = by_title.get(s.title)
        if o:
            s.reflection = o.get("reflection", s.reflection)
            s.connection = o.get("connection", s.connection)
