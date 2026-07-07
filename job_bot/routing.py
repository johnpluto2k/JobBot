"""Phase 5: geographic + platform routing.

Classifies a job's market tier, recommends a platform/application strategy, and
computes a priority score for the monitoring queue — so high-tier, high-fit,
fresh postings rise to the top.
"""

from __future__ import annotations

import re

from .jd_models import JobPosting
from .skills_ontology import MARKET_TIERS

# Job-board source -> how to play it (from the master plan's platform strategy).
PLATFORM_STRATEGY: dict[str, str] = {
    "linkedin": "Easy Apply: high volume, low friction — apply fast, light tailoring.",
    "indeed": "Best scraper, no rate limiting — good for monitoring; standard tailoring.",
    "glassdoor": "Pair postings with salary data before applying/negotiating.",
    "google": "Aggregator — follow through to the company portal for the real ATS.",
    "zip_recruiter": "Volume board — quick apply, verify the role is current.",
    "handshake": "Critical for UMD: Big 4 / Fortune 500 recruit here — full tailoring.",
    "workday": "Company portal, high stakes — full tailoring, exact-keyword resume.",
}

# ATS portal -> tailoring intensity
FULL_TAILORING_ATS = {"Workday", "Taleo", "iCIMS", "SuccessFactors"}


def classify_tier(location: str | None, remote: bool = False) -> tuple[str, int]:
    low = (location or "").lower()
    for label, cfg in MARKET_TIERS.items():
        for token in cfg["cities"] + cfg["states"]:
            if re.search(rf"(?<![a-z]){re.escape(token)}(?![a-z])", low):
                return label, cfg["tier"]
    if remote or "remote" in low:
        return "Remote", 0
    return "Other / Out-of-market", 4


def tier_weight(tier_num: int) -> float:
    return {1: 1.0, 2: 0.8, 0: 0.7, 3: 0.55, 4: 0.3}.get(tier_num, 0.4)


def platform_action(job: JobPosting) -> str:
    if job.ats_platform in FULL_TAILORING_ATS:
        return (f"{job.ats_platform} portal → FULL tailoring required "
                "(exact keywords, single-column resume).")
    if job.source_url and "linkedin.com" in (job.source_url or ""):
        return PLATFORM_STRATEGY["linkedin"]
    return "Standard tailoring; confirm the real ATS on the company portal."


def priority_score(tier_num: int, ats_score: float, days_since_posting: int | None) -> float:
    """0..100 priority for the monitoring queue."""
    tier = tier_weight(tier_num)
    fit = max(0.0, min(1.0, ats_score / 100.0))
    recency = 1.0
    if days_since_posting is not None:
        if days_since_posting <= 1:
            recency = 1.0
        elif days_since_posting <= 3:
            recency = 0.9
        elif days_since_posting <= 7:
            recency = 0.75
        elif days_since_posting <= 21:
            recency = 0.5
        else:
            recency = 0.3
    return round(100.0 * (0.45 * tier + 0.40 * fit + 0.15 * recency), 1)


# --- Apply gate (career-ops "don't apply below X" philosophy) ----------------
# career-ops refuses anything scoring below 4.0/5 — quality over quantity. John's
# ATS scores run lower than a senior candidate's, so the gate keys off the blended
# priority (tier + fit + recency) and the legitimacy score, calibrated to his data:
# he applied to 101 positions for an 11% interview rate — a gate focuses that effort.
APPLY_THRESHOLD = 60.0    # priority at/above this = a clear apply
MAYBE_THRESHOLD = 45.0    # between the two = worth it only with an edge (warm contact)
LEGIT_MIN = 50            # below this legitimacy score, verify before spending time


def recommend(priority: float, legit_score: int | None = None,
              has_warm_contacts: bool = False, seniority: str | None = None,
              on_target: bool = True) -> tuple[str, str]:
    """career-ops-style apply gate → (recommendation, reason).

    Returns one of: "🎓 Above level" | "🚩 Verify" | "✅ Apply" | "🟡 Maybe" | "⏭️ Skip".
    Gates, in order, so the pipeline stays aimed at who John actually is:
      1. seniority — an entry-level candidate is never told to apply to a
         senior/lead/exec role; a mid-level role is capped at "Maybe".
      2. legitimacy — scam/ghost postings need verifying first.
      3. field fit — a role outside John's target fields ('Other') is never a
         clean "Apply", only "Maybe" at best.
      4. priority — tier + ATS fit + recency for the roles that pass 1-3.
    """
    if seniority in ("senior", "lead", "exec"):
        return "🎓 Above level", ("this is a senior/management role — you're targeting "
                                  "entry-level, so it's out of range")
    if legit_score is not None and legit_score < LEGIT_MIN:
        return "🚩 Verify", "flagged as possible scam/ghost — confirm it's real before applying"
    if seniority == "mid":
        return "🟡 Maybe", "a mid-level role — a stretch for a new grad, apply only if it's a strong fit"
    if not on_target:
        if has_warm_contacts:
            return "🟡 Maybe", "outside your target fields, but you have a warm contact here"
        if priority >= MAYBE_THRESHOLD:
            return "🟡 Maybe", "outside your target fields — apply only if it genuinely fits your goals"
        return "⏭️ Skip", "outside your target fields and low priority"
    if priority >= APPLY_THRESHOLD:
        return "✅ Apply", f"on-target, entry-level, strong fit + tier + freshness (priority {priority:.0f})"
    if priority >= MAYBE_THRESHOLD or has_warm_contacts:
        why = "you have a warm contact here — network in" if has_warm_contacts \
            else f"borderline (priority {priority:.0f}) — apply only if it's a genuine target"
        return "🟡 Maybe", why
    return "⏭️ Skip", f"low priority ({priority:.0f}) — your time is better spent on higher-fit roles"


def route(job: JobPosting, ats_score: float,
          days_since_posting: int | None = None,
          legit_score: int | None = None,
          seniority: str | None = None,
          on_target: bool = True) -> dict:
    tier_label, tier_num = classify_tier(job.location, job.remote)
    priority = priority_score(tier_num, ats_score, days_since_posting)
    rec, rec_why = recommend(priority, legit_score, seniority=seniority, on_target=on_target)
    return {
        "market_tier": tier_label,
        "tier_num": tier_num,
        "priority": priority,
        "platform_action": platform_action(job),
        "tailoring": "full" if job.ats_platform in FULL_TAILORING_ATS else "standard",
        "recommendation": rec,
        "recommendation_reason": rec_why,
        "seniority": seniority,
    }
