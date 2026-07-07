"""Rejection analysis (recommendation #9).

Logs rejections (manually or auto from inbox triage), enriching each with the
ATS score, market tier, and platform already on file for that company, then
surfaces patterns over time — which stage rejects you most, at what ATS score,
and which role types — so the system can sharpen targeting.
"""

from __future__ import annotations

from collections import Counter
from datetime import date

from .db import connect

# Pipeline stages, earliest → latest.
STAGES = ["ats_screen", "assessment", "recruiter_screen", "first_round", "superday", "final",
          "unknown"]

STAGE_MEANING = {
    "ats_screen": "auto-filtered before a human — improve ATS match + keyword tailoring",
    "assessment": "online assessment / HireVue — drill that format (interview --drill)",
    "recruiter_screen": "recruiter fit/logistics — tighten your pitch and 'why this firm'",
    "first_round": "first-round behavioral/fit — strengthen the story bank",
    "superday": "final/superday — technical depth or executive presence",
    "final": "final round — differentiation and close",
    "unknown": "stage not recorded — log the stage to sharpen this analysis",
}

# Map a job/job-status to the rejection stage it implies.
STATUS_TO_STAGE = {
    "new": "ats_screen", "applied": "ats_screen", "networking": "recruiter_screen",
    "interview": "first_round",
}

ROLE_TYPE_KEYWORDS = [
    ("IT Audit / Technology Risk", ["it audit", "technology risk", "it risk", "itgc"]),
    ("Audit / Assurance", ["audit", "assurance"]),
    ("Tax", ["tax"]),
    ("Data Analytics", ["data analyst", "data analytics", "analytics", "bi ", "business intelligence"]),
    ("FP&A / Corporate Finance", ["fp&a", "financial analyst", "corporate finance", "finance"]),
    ("FinTech", ["fintech", "risk operations", "payments"]),
    ("Software Engineering", ["software", "developer", "engineer"]),
]


def role_type_from_title(title: str | None) -> str | None:
    if not title:
        return None
    low = title.lower()
    for rt, kws in ROLE_TYPE_KEYWORDS:
        if any(k in low for k in kws):
            return rt
    return None


def _enrich(con, company: str | None) -> dict:
    """Pull ATS score / tier / platform / title already known for this company."""
    out = {"ats_score": None, "market_tier": None, "platform": None, "role_title": None}
    if not company:
        return out
    like = f"%{company.lower()}%"
    j = con.execute("SELECT ats_score, market_tier, site, title FROM jobs "
                    "WHERE lower(company) LIKE ? ORDER BY priority DESC LIMIT 1", (like,)).fetchone()
    if j:
        out.update(ats_score=j["ats_score"], market_tier=j["market_tier"],
                   platform=j["site"], role_title=j["title"])
    d = con.execute("SELECT ats_score FROM decisions WHERE lower(company) LIKE ? "
                    "ORDER BY created_at DESC LIMIT 1", (like,)).fetchone()
    if d and out["ats_score"] in (None, 0):
        out["ats_score"] = d["ats_score"]
    return out


def log_rejection(company: str | None, role_title: str | None = None, stage: str | None = None,
                  ats_score: float | None = None, role_type: str | None = None,
                  market_tier: str | None = None, platform: str | None = None,
                  source: str = "manual", rejected_on: str | None = None,
                  notes: str | None = None) -> int:
    con = connect()
    enr = _enrich(con, company)
    role_title = role_title or enr["role_title"]
    rec = {
        "company": company,
        "role_title": role_title,
        "role_type": role_type or role_type_from_title(role_title),
        "stage": stage or "unknown",
        "ats_score": ats_score if ats_score is not None else enr["ats_score"],
        "market_tier": market_tier or enr["market_tier"],
        "platform": platform or enr["platform"],
        "source": source,
        "rejected_on": rejected_on or date.today().isoformat(),
        "notes": notes,
    }
    cur = con.execute(
        "INSERT INTO rejections (company, role_title, role_type, stage, ats_score, market_tier, "
        "platform, source, rejected_on, notes) VALUES "
        "(:company,:role_title,:role_type,:stage,:ats_score,:market_tier,:platform,:source,"
        ":rejected_on,:notes)", rec)
    con.commit()
    rid = cur.lastrowid
    con.close()
    return rid


def _band(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= 80:
        return "80+ strong"
    if score >= 65:
        return "65–79 solid"
    if score >= 50:
        return "50–64 moderate"
    return "<50 weak"


def analyze() -> dict:
    con = connect()
    rows = [dict(r) for r in con.execute("SELECT * FROM rejections")]
    con.close()
    if not rows:
        return {"total": 0}

    by_stage = Counter(r["stage"] or "unknown" for r in rows)
    by_role = Counter(r["role_type"] or "unknown" for r in rows)
    by_tier = Counter(r["market_tier"] or "unknown" for r in rows)
    by_platform = Counter(r["platform"] or "unknown" for r in rows)
    scores = [r["ats_score"] for r in rows if r["ats_score"] is not None]
    by_band = Counter(_band(r["ats_score"]) for r in rows)

    insights, recs = [], []

    # Dominant stage
    top_stage, n = by_stage.most_common(1)[0]
    insights.append(f"{n}/{len(rows)} rejections occur at the '{top_stage}' stage — "
                    f"{STAGE_MEANING.get(top_stage, '')}.")
    if top_stage == "ats_screen":
        recs.append("You're losing most at the resume/ATS screen — raise ATS match before "
                    "applying (run `score_job`, then `generate` to tailor) and prioritize "
                    "network-first verdicts.")
    elif top_stage in ("first_round", "superday", "final", "recruiter_screen", "assessment"):
        recs.append(f"You're reaching interviews but converting poorly at '{top_stage}' — "
                    "drill that stage (`interview --drill` / `--mock`) and review the rubric.")

    # ATS correlation
    if scores:
        avg = sum(scores) / len(scores)
        insights.append(f"Average ATS match on rejected apps: {avg:.0f} "
                        f"(band breakdown: {dict(by_band)}).")
        if avg < 60:
            recs.append("Rejections cluster at low ATS scores — only cold-apply above ~65; "
                        "below that, tailor harder or network first.")

    # Role-type concentration
    if by_role and by_role.most_common(1)[0][0] != "unknown":
        rt, rn = by_role.most_common(1)[0]
        if rn >= 2:
            insights.append(f"Most rejections are in '{rt}' ({rn}).")
            recs.append(f"Reassess fit/targeting for '{rt}' roles, or invest in the gaps that "
                        "role keeps surfacing.")

    return {
        "total": len(rows),
        "by_stage": dict(by_stage),
        "by_role_type": dict(by_role),
        "by_tier": dict(by_tier),
        "by_platform": dict(by_platform),
        "by_ats_band": dict(by_band),
        "avg_ats_score": round(sum(scores) / len(scores), 1) if scores else None,
        "insights": insights,
        "recommendations": recs,
    }
