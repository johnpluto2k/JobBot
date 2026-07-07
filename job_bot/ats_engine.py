"""Reverse ATS scoring engine.

Scores the master profile against a parsed JobPosting the way an ATS would:
keyword coverage, title alignment, quantification, and content similarity —
weighted per detected ATS platform — then produces a ranked, actionable gap
analysis ("which keyword to add, where, and why").
"""

from __future__ import annotations

import json
from pathlib import Path

from . import config
from .ats_platforms import get_platform
from .jd_models import ATSScoreReport, GapItem, JobPosting, KeywordHit, SubScores
from .similarity import contains_phrase, tfidf_cosine, tokenize, content_similarity
from .skills_ontology import SKILL_ALIASES

TECH_SKILLS = {"sql", "python", "r", "excel", "power bi", "tableau", "vba", "alteryx",
               "sap", "javascript", "etl", "data visualization", "machine learning",
               "cybersecurity"}


# --------------------------------------------------------------------------- #
# Profile loading / flattening
# --------------------------------------------------------------------------- #
def load_profile(path: Path | None = None) -> dict:
    path = Path(path) if path else config.PROFILE_JSON
    if not path.exists():
        raise SystemExit(
            f"No profile at {path}. Run `python -m job_bot.build_profile` first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def profile_sections(profile: dict) -> dict[str, str]:
    """label -> searchable text, used for keyword attribution and gap targeting."""
    sections: dict[str, str] = {}
    for e in profile.get("experience", []):
        label = f"Experience — {e.get('role') or ''} at {e.get('organization') or ''}".strip()
        body = " ".join(b.get("text", "") for b in e.get("bullets", []))
        sections[label] = f"{e.get('role','')} {body}"
    for l in profile.get("leadership", []):
        label = f"Leadership — {l.get('role') or ''} at {l.get('organization') or ''}".strip()
        body = " ".join(b.get("text", "") for b in l.get("bullets", []))
        sections[label] = f"{l.get('role','')} {body}"
    for pr in profile.get("projects", []):
        label = f"Project — {pr.get('name') or ''}".strip()
        body = (pr.get("description") or "") + " " + " ".join(
            b.get("text", "") for b in pr.get("bullets", [])
        ) + " " + " ".join(pr.get("technologies", []))
        sections[label] = body
    edu = profile.get("education", [])
    if edu:
        sections["Education"] = " ".join(
            (e.get("degree") or "") + " " + " ".join(e.get("relevant_coursework", []))
            for e in edu
        )
    skills = [s for grp in profile.get("skills", []) for s in grp.get("skills", [])]
    if skills:
        sections["Skills"] = ", ".join(skills)
    certs = profile.get("certifications", [])
    if certs:
        sections["Certifications"] = ", ".join(certs)
    return sections


def profile_text(profile: dict) -> str:
    parts = list(profile_sections(profile).values())
    parts.append(profile.get("summary") or "")
    return "\n".join(parts)


def candidate_skills(text: str) -> set[str]:
    low = text.lower()
    return {
        canon for canon, aliases in SKILL_ALIASES.items()
        if any(contains_phrase(low, a) for a in aliases)
    }


def _all_bullets(profile: dict) -> list[dict]:
    out: list[dict] = []
    for key in ("experience", "leadership"):
        for e in profile.get(key, []):
            out.extend(e.get("bullets", []))
    for pr in profile.get("projects", []):
        out.extend(pr.get("bullets", []))
    return out


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #
def _where(keyword: str, sections: dict[str, str]) -> str | None:
    aliases = SKILL_ALIASES.get(keyword, [keyword])
    for label, text in sections.items():
        low = text.lower()
        if any(contains_phrase(low, a) for a in aliases):
            return label
    return None


def _best_target(keyword: str, sections: dict[str, str]) -> tuple[str | None, float]:
    """Section whose content is most related to the keyword (where to add it)."""
    query = keyword + " " + " ".join(SKILL_ALIASES.get(keyword, []))
    best, best_sim = None, 0.0
    for label, text in sections.items():
        if label == "Skills":
            continue
        sim = tfidf_cosine(query, text)
        if sim > best_sim:
            best, best_sim = label, sim
    return best, best_sim


def _title_alignment(job: JobPosting, profile: dict, corpus_tokens: set[str]) -> float:
    if not job.title:
        return 0.5
    title_tokens = [t for t in tokenize(job.title)]
    if not title_tokens:
        return 0.5
    overlap = sum(1 for t in title_tokens if t in corpus_tokens) / len(title_tokens)
    targets = [t.lower() for t in profile.get("targets", {}).get("target_roles", [])]
    role_bonus = 0.0
    if job.role_type and any(job.role_type.lower() in t or t in job.role_type.lower()
                             for t in targets):
        role_bonus = 1.0
    return round(0.7 * overlap + 0.3 * role_bonus, 4)


def _quantification(profile: dict, jd_keywords: set[str]) -> tuple[float, str]:
    bullets = _all_bullets(profile)
    if not bullets:
        return 0.0, "No bullets found in profile."
    # Relevance by scanning bullet text for any JD-keyword alias (Phase 1's
    # keyword_tags are sparse); fall back to all bullets if nothing matches.
    aliases = {a for kw in jd_keywords for a in SKILL_ALIASES.get(kw, [kw])}
    relevant = [b for b in bullets
                if any(contains_phrase(b.get("text", "").lower(), a) for a in aliases)]
    pool = relevant or bullets
    scope = "JD-relevant" if relevant else "resume"
    quant = sum(1 for b in pool if b.get("quantified"))
    frac = quant / len(pool)
    note = f"{quant}/{len(pool)} {scope} bullets are quantified ({frac*100:.0f}%)."
    if frac < 0.5:
        note += " Add metrics ($, %, counts) to more bullets."
    return round(frac, 4), note


def score(job: JobPosting, profile: dict) -> ATSScoreReport:
    sections = profile_sections(profile)
    text = profile_text(profile)
    cand = candidate_skills(text)
    corpus_tokens = set(tokenize(text))
    platform = get_platform(job.ats_platform)

    # --- keyword coverage (weighted: required 1.0, preferred 0.5) ---
    matched, missing = [], []
    weight_total = weight_hit = 0.0
    for kw in job.required_keywords:
        w = 1.0
        weight_total += w
        present = kw in cand
        hit = KeywordHit(keyword=kw, importance="required", present=present,
                         where=_where(kw, sections) if present else None)
        if present:
            weight_hit += w
            matched.append(hit)
        else:
            missing.append(hit)
    for kw in job.preferred_keywords:
        w = 0.5
        weight_total += w
        present = kw in cand
        hit = KeywordHit(keyword=kw, importance="preferred", present=present,
                         where=_where(kw, sections) if present else None)
        if present:
            weight_hit += w
            matched.append(hit)
        else:
            missing.append(hit)
    keyword_coverage = (weight_hit / weight_total) if weight_total else 0.5

    title_alignment = _title_alignment(job, profile, corpus_tokens)
    jd_kw_set = set(job.all_keywords)
    quantification, quant_note = _quantification(profile, jd_kw_set)
    similarity = content_similarity(text, job.raw_text)

    # --- platform-weighted overall ---
    w = (platform.w_keyword, platform.w_title, platform.w_quantification, platform.w_similarity)
    wsum = sum(w) or 1.0
    overall = 100.0 * (
        w[0] * keyword_coverage + w[1] * title_alignment
        + w[2] * quantification + w[3] * similarity
    ) / wsum

    # --- gap analysis (rank missing by impact) ---
    gaps: list[GapItem] = []
    for hit in missing:
        kw = hit.keyword
        base_w = 1.0 if hit.importance == "required" else 0.5
        impact = (base_w / weight_total * platform.w_keyword / wsum) if weight_total else 0.0
        target, sim = _best_target(kw, sections)
        if kw in TECH_SKILLS:
            section = "Skills"
            target_label = "Skills section"
            action = f"Add '{kw}' to your Skills section" + (
                " and evidence it in a bullet/project." if hit.importance == "required" else ".")
        elif target and sim >= 0.12:
            section = target
            target_label = target
            action = (f"Weave '{kw}' into {target} — your closest relevant experience"
                      f"{' (exact phrasing matters here)' if platform.exact_match else ''}.")
        else:
            section = "Experience / Projects"
            target_label = target if sim >= 0.06 else None
            hint = f" (closest existing material: {target})" if target_label else ""
            action = (f"Add a bullet or project demonstrating '{kw}' if you genuinely "
                      f"have it{hint}.")
        gaps.append(GapItem(
            keyword=kw, importance=hit.importance, impact=round(impact, 4),
            suggested_section=section, suggested_target=target_label, action=action,
        ))
    gaps.sort(key=lambda g: (g.importance != "required", -g.impact))

    report = ATSScoreReport(
        overall_score=round(overall, 1),
        verdict=_verdict(overall),
        subscores=SubScores(
            keyword_coverage=round(keyword_coverage, 4),
            title_alignment=title_alignment,
            quantification=quantification,
            content_similarity=round(similarity, 4),
        ),
        ats_platform=platform.name,
        platform_weighting=platform.summary,
        platform_tips=platform.tips,
        matched_keywords=sorted(matched, key=lambda h: h.importance != "required"),
        missing_keywords=missing,
        gap_analysis=gaps,
        quantification_note=quant_note,
        job=job,
    )
    return report


def _verdict(score: float) -> str:
    if score >= 80:
        return "🟢 Strong match — apply with confidence."
    if score >= 65:
        return "🟡 Solid match — close the top 1–2 gaps, then apply."
    if score >= 50:
        return "🟠 Moderate — meaningful tailoring needed before applying."
    return "🔴 Weak match — significant gaps; tailor heavily or reconsider fit."
