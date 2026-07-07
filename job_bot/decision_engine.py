"""Network-vs-cold-apply decision engine.

Combines four signals into a verdict:
  * competition / applicant volume (company prestige, seniority, recency, niche)
  * resume strength (Phase 2 ATS overall score)
  * connection leverage (warm contacts at the company)
  * posting recency (apply-fast advantage)

Verdicts (from the master plan):
  🟢 cold_apply · 🟡 apply_and_network · 🔴 network_first
"""

from __future__ import annotations

from .decision_models import (
    VERDICT_LABELS,
    ConnectionMatch,
    DecisionReport,
    Factors,
)
from .jd_models import JobPosting

# Company prestige → applicant-volume pressure (0..1). Keyword-matched.
HIGH_PRESTIGE = [
    "deloitte", "pwc", "pricewaterhouse", "ey", "ernst", "kpmg",        # Big 4
    "goldman", "jpmorgan", "morgan stanley", "j.p. morgan",            # IB
    "google", "meta", "facebook", "microsoft", "amazon", "apple", "netflix",
    "stripe", "plaid", "robinhood", "block", "nvidia", "openai",       # top tech/fintech
]
MID_PRESTIGE = [
    "capital one", "fannie", "freddie", "booz", "accenture", "protiviti",
    "grant thornton", "rsm", "bdo", "cohnreznick", "alvarez", "marsal", "xometry",
]

# Niche/specific roles draw fewer (but more targeted) applicants.
NICHE_ROLES = {"IT Audit / Technology Risk", "Tax", "FP&A / Corporate Finance",
               "Audit / Assurance"}
BROAD_ROLES = {"Data Analytics", "Software Engineering", "FinTech"}


def _prestige(company: str | None) -> float:
    c = (company or "").lower()
    if any(k in c for k in HIGH_PRESTIGE):
        return 0.9
    if any(k in c for k in MID_PRESTIGE):
        return 0.55
    return 0.4 if c else 0.45


def estimate_competition(job: JobPosting, days_since_posting: int | None) -> tuple[float, list[str]]:
    notes: list[str] = []
    prestige = _prestige(job.company)
    score = 0.30 + 0.30 * prestige
    if prestige >= 0.9:
        notes.append(f"{job.company or 'This employer'} is high-prestige — heavy applicant volume.")

    sen = (job.seniority or "mid").lower()
    sen_adj = {"intern": 0.15, "entry": 0.12, "mid": 0.0, "senior": -0.10}.get(sen, 0.0)
    score += sen_adj
    if sen in ("intern", "entry"):
        notes.append("Entry-level/intern roles attract the largest applicant pools.")

    if job.remote:
        score += 0.10
        notes.append("Remote/hybrid widens the applicant pool (nationwide competition).")

    if job.role_type in NICHE_ROLES:
        score -= 0.08
        notes.append(f"'{job.role_type}' is a specialized track — fewer, more targeted applicants.")
    elif job.role_type in BROAD_ROLES:
        score += 0.05

    if days_since_posting is not None:
        if days_since_posting <= 2:
            notes.append("Posted <48h ago — early-applicant advantage; move fast.")
        elif days_since_posting >= 14:
            score += 0.10
            notes.append(f"Posted {days_since_posting} days ago — applicant pool is already deep.")
        elif days_since_posting >= 7:
            score += 0.05

    return max(0.1, min(0.95, round(score, 3))), notes


def decide(job: JobPosting, ats_score: float, matches: list[ConnectionMatch],
           days_since_posting: int | None = None) -> DecisionReport:
    from .connections import connection_strength

    competition, comp_notes = estimate_competition(job, days_since_posting)
    resume_strength = max(0.0, min(1.0, ats_score / 100.0))
    conn_strength, recruiter = connection_strength(matches)

    factors = Factors(
        competition=competition,
        resume_strength=round(resume_strength, 3),
        connection_strength=conn_strength,
        recruiter_available=recruiter,
        days_since_posting=days_since_posting,
        competition_notes=comp_notes,
    )

    verdict, rationale, confidence = _verdict(competition, resume_strength, conn_strength, recruiter)

    actions = _actions(verdict, job, matches, factors)
    report = DecisionReport(
        verdict=verdict,
        verdict_label=VERDICT_LABELS[verdict],
        confidence=round(confidence, 2),
        rationale=rationale,
        factors=factors,
        top_contacts=matches[:3],
        recommended_actions=actions,
        company=job.company,
        title=job.title,
        ats_score=round(ats_score, 1),
    )
    return report


def _verdict(competition: float, resume: float, conn: float,
             recruiter: bool) -> tuple[str, str, float]:
    # 🔴 Strong leverage + tough competition → spend the connection before applying.
    if conn >= 0.5 and competition >= 0.5:
        return ("network_first",
                f"You have real warm leverage (connection {conn:.2f}) into a high-competition "
                f"role (competition {competition:.2f}). A referral materially beats a cold app here — "
                "get it before submitting.",
                0.8 if recruiter else 0.7)

    # 🟡 Some warmth → don't sit on it, but don't wait either.
    if conn >= 0.35:
        return ("apply_and_network",
                f"You have a usable contact (connection {conn:.2f}). Submit now and reach out in "
                "parallel so a warm intro can pull your application from the pile.",
                0.65)

    # 🟢 Beatable competition + a strong-enough resume → just apply.
    if competition <= 0.5 and resume >= 0.55:
        return ("cold_apply",
                f"Manageable competition ({competition:.2f}) and a solid resume match "
                f"({resume:.2f}) — a cold application is worth submitting on its own.",
                0.7)

    # 🟡 High competition but no warm contact yet → apply and build a way in.
    if competition >= 0.6:
        return ("apply_and_network",
                f"Competition is high ({competition:.2f}) and you have no warm contact yet. Apply, "
                "but actively try to source a UMD/PSE alum at the company to follow up through.",
                0.6)

    # 🟢 Low-stakes default.
    return ("cold_apply",
            f"Competition is moderate ({competition:.2f}) and no strong connection exists — "
            "a cold application is a reasonable first move.",
            0.55)


def _actions(verdict: str, job: JobPosting, matches: list[ConnectionMatch],
             f: Factors) -> list[str]:
    actions: list[str] = []
    company = job.company or "the company"

    if verdict == "network_first":
        top = matches[0] if matches else None
        if top:
            actions.append(
                f"Reach out to {top.name} ({top.title or 'contact'} at {company}) for a referral "
                f"before applying — your warmest tie ({top.relationship}, warmth {top.warmth:.2f}).")
        actions.append("Send a short, specific referral request (shared UMD/PSE/IEFS background + "
                       "the exact role) — the Phase 6 outreach drafter will template this.")
        actions.append("Once the referral is in, submit the tailored resume from Phase 2.")
    elif verdict == "apply_and_network":
        actions.append("Submit your tailored application now — don't wait on networking.")
        if matches:
            top = matches[0]
            actions.append(f"In parallel, message {top.name} ({top.relationship}) to flag your "
                           "application and ask for an internal nudge.")
        else:
            actions.append(f"Search LinkedIn for UMD / Pi Sigma Epsilon alums at {company} and "
                           "send a brief intro to build a warm path for follow-up.")
    else:  # cold_apply
        actions.append("Submit your tailored application — cold is fine here.")
        actions.append("Set a 5–7 day follow-up reminder; if no response, look for a warm contact then.")

    if f.days_since_posting is not None and f.days_since_posting <= 2:
        actions.insert(0, "⏱ Posted <48h ago — prioritize this today; early applicants get seen first.")
    if job.gpa_cutoff:
        actions.append(f"Note: this posting implies a GPA cutoff ~{job.gpa_cutoff}; confirm you clear it.")
    return actions
