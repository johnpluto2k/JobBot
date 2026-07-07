"""Automated growth plan — turns John's skill gaps + where he's actually applying
into concrete, prioritized next moves: certifications to pursue, portfolio
projects to build, and tailored resume variants to maintain.

It reuses the same skill ontology the ATS scorer uses, so "what's missing" here
is exactly what an ATS would dock him for. The plan is recomputed from the live
profile + application history every time, so it stays honest as he improves.
"""

from __future__ import annotations

from .applications import build_applications, classify_field
from .ats_engine import candidate_skills, load_profile, profile_text

# What a strong candidate in each field has on their resume (canonical skills).
FIELD_IDEAL: dict[str, list[str]] = {
    "IT Audit / Tech Risk": ["it audit", "internal controls", "sox", "risk management",
                             "cybersecurity", "sql", "excel", "data analysis", "auditing",
                             "compliance"],
    "Audit & Assurance": ["auditing", "internal controls", "gaap", "financial reporting",
                          "cpa", "excel", "accounting", "data analysis"],
    "Internal Audit": ["auditing", "internal controls", "sox", "risk management", "compliance",
                       "excel", "data analysis"],
    "Tax": ["tax", "accounting", "cpa", "excel", "compliance", "financial reporting"],
    "Data & Analytics": ["sql", "python", "excel", "data analysis", "data visualization",
                         "power bi", "tableau", "statistics", "etl"],
    "Finance / FP&A": ["fp&a", "financial analysis", "excel", "financial reporting", "accounting",
                       "data analysis", "gaap"],
    "Risk & Compliance": ["risk management", "compliance", "internal controls", "sox", "auditing",
                          "data analysis"],
}

# Certifications worth pursuing per field: (name, why, effort).
FIELD_CERTS: dict[str, list[tuple[str, str, str]]] = {
    "IT Audit / Tech Risk": [
        ("ISACA Student Membership → CISA (after grad)", "CISA is THE IT-audit credential; "
         "student membership now signals intent and unlocks free resources.", "now / long-term"),
        ("CompTIA Security+", "Validates the security-controls & cyber knowledge IT-audit JDs list.",
         "1–2 months"),
        ("ITGC / IT audit micro-course (ISACA or Coursera)", "Lets you put 'ITGC, access & change "
         "management' on the resume with substance behind it.", "weeks"),
    ],
    "Audit & Assurance": [
        ("CPA eligibility (in progress)", "Already on track — keep the 150-credit plan visible.", "ongoing"),
        ("Audit Data Analytics (e.g., Deloitte/EY virtual or Coursera)", "Big 4 audit is analytics-"
         "heavy now; shows you can audit with data, not just tie out.", "weeks"),
        ("Excel / Power Query for auditors", "Workpaper automation is an expected baseline.", "weeks"),
    ],
    "Internal Audit": [
        ("IIA Student / CIA track", "The internal-audit credential; student membership is cheap.",
         "now / long-term"),
        ("COSO & risk-assessment micro-course", "Lets you speak the internal-controls framework "
         "language IA teams expect.", "weeks"),
    ],
    "Tax": [
        ("CPA eligibility (in progress)", "Core for tax track — keep it front and center.", "ongoing"),
        ("VITA/TCE certification (via TerpTax)", "You already do this — make sure it's a resume bullet.",
         "have it"),
    ],
    "Data & Analytics": [
        ("Google Data Analytics Professional Certificate", "Recognized entry credential; covers the "
         "full SQL→clean→viz workflow.", "1–2 months"),
        ("Microsoft Power BI (PL-300) or Tableau Desktop Specialist", "Names a viz tool on your "
         "resume — your biggest analytics gap.", "1 month"),
        ("SQL certificate (DataCamp / Mode SQL)", "Proves the SQL you already use.", "weeks"),
    ],
    "Finance / FP&A": [
        ("CFI FMVA or a financial-modeling course", "Signals 3-statement / DCF modeling for FP&A.",
         "1–2 months"),
        ("Bloomberg Market Concepts (BMC)", "Cheap, fast, recognized markets credential.", "~10 hrs"),
    ],
    "Risk & Compliance": [
        ("ISACA CRISC (long-term) / risk micro-course", "Names enterprise-risk fluency.", "long-term"),
    ],
}

# Portfolio project ideas keyed by the gap skill they close. Concrete + résumé-able.
GAP_PROJECTS: dict[str, str] = {
    "it audit": "Run a mini ITGC review: document access-management + change-management controls "
                "for a sample app, test them, and write a one-page audit workpaper.",
    "sox": "Build a SOX control matrix in Excel (risk → control → test → evidence) for a revenue "
           "process, with an automated testing tab.",
    "risk management": "Write a 2-page risk assessment (risk register + heat map) for a process you "
                       "know first-hand — e.g., leasing operations at The Scion Group.",
    "cybersecurity": "Complete a hands-on access-controls lab (TryHackMe / ISACA) and summarize the "
                     "findings in audit-control language.",
    "power bi": "Build a Power BI dashboard on a public dataset (audit findings, fraud cases, or "
                "spending) with a KPI page and drill-through.",
    "tableau": "Recreate a financial-statement or risk dashboard in Tableau Public and publish it to "
               "your profile.",
    "excel": "Build an automated reconciliation / variance workbook (pivot tables + a macro) and "
             "document the control it enforces.",
    "data analysis": "Do a Benford's-Law anomaly analysis on a public expense dataset in Python and "
                     "write the findings up like an audit memo.",
    "etl": "Build a small Python ETL that pulls a public dataset, cleans it, and loads it to SQL — "
           "reuse the Supabase/Postgres skills from Pantry Plate.",
    "financial analysis": "Build a 3-statement model + DCF for a public company in Excel.",
    "fp&a": "Build a budget-vs-actual variance model with a rolling forecast tab.",
    "gaap": "Write up 3 short technical-accounting memos (revenue recognition, leases, impairment) "
            "citing the relevant ASC.",
}

# Map John's stated target roles to fields so the plan always covers his goals,
# even in fields he hasn't applied to yet.
TARGET_ROLE_FIELDS = {
    "it audit": "IT Audit / Tech Risk", "technology risk": "IT Audit / Tech Risk",
    "fintech": "Risk & Compliance", "data analytics": "Data & Analytics",
    "fp&a": "Finance / FP&A", "big 4 audit": "Audit & Assurance", "audit": "Audit & Assurance",
}

PRETTY_SKILL = {"it audit": "IT audit (ITGC/SOX)", "sox": "SOX", "fp&a": "FP&A",
                "gaap": "US GAAP", "etl": "ETL / data pipelines", "power bi": "Power BI"}


def _pretty(skill: str) -> str:
    return PRETTY_SKILL.get(skill, skill.title() if len(skill) > 3 else skill.upper())


def _target_fields(profile: dict) -> list[str]:
    """Fields John says he's targeting (from his profile)."""
    out: list[str] = []
    for role in profile.get("targets", {}).get("target_roles", []):
        low = role.lower()
        for key, field in TARGET_ROLE_FIELDS.items():
            if key in low and field not in out:
                out.append(field)
    return out


def build_plan(profile: dict | None = None) -> dict:
    """Compute the prioritized growth plan from the live profile + applications."""
    profile = profile or load_profile()
    have = candidate_skills(profile_text(profile))

    apps = build_applications()
    applied_fields: dict[str, int] = {}
    for a in apps:
        applied_fields[a["field"]] = applied_fields.get(a["field"], 0) + 1
    applied_fields.pop("Other", None)

    target_fields = _target_fields(profile)
    # Focus = stated targets first, then the fields he actually applies to most.
    focus: list[str] = list(target_fields)
    for f, _ in sorted(applied_fields.items(), key=lambda kv: -kv[1]):
        if f not in focus:
            focus.append(f)
    focus = [f for f in focus if f in FIELD_IDEAL][:4]

    per_field = []
    for field in focus:
        ideal = FIELD_IDEAL.get(field, [])
        gaps = [s for s in ideal if s not in have]
        strengths = [s for s in ideal if s in have]
        projects = [GAP_PROJECTS[g] for g in gaps if GAP_PROJECTS.get(g)][:2]
        per_field.append({
            "field": field,
            "applied_count": applied_fields.get(field, 0),
            "is_stated_target": field in target_fields,
            "strengths": [_pretty(s) for s in strengths],
            "gaps": [_pretty(s) for s in gaps],
            "gaps_raw": gaps,
            "certifications": FIELD_CERTS.get(field, []),
            "projects": projects,
            "resume_variant": {
                "name": f"{field} résumé",
                "lead_with": [_pretty(s) for s in strengths][:6],
                "add_keywords": [_pretty(s) for s in gaps][:5],
            },
        })

    # Cross-cutting insights.
    insights: list[str] = []
    it_applied = applied_fields.get("IT Audit / Tech Risk", 0)
    if "IT Audit / Tech Risk" in target_fields and it_applied == 0:
        insights.append("**IT Audit is your #1 stated target but 0 of your applications were "
                        "IT-audit-titled roles.** Either apply to more IT-audit / technology-risk "
                        "postings, or your funnel will keep routing you to Tax/Audit.")
    if "excel" not in have:
        insights.append("Excel wasn't detected on your résumé — it's now added to your skills, but "
                        "back it with a bullet (the ATS weights demonstrated skills).")
    has_tableau = "tableau" in have
    has_powerbi = "power bi" in have
    if not has_tableau and not has_powerbi:
        insights.append("No data-viz tool (Power BI / Tableau) on your résumé — the single "
                        "highest-leverage add for both Data-Analytics and modern-audit roles.")
    elif not (has_tableau and has_powerbi):
        have_tool = "Tableau" if has_tableau else "Power BI"
        insights.append(f"You have {have_tool} listed — now **prove it**: publish one dashboard "
                        f"(risk/audit-findings dataset) to your portfolio, and consider adding "
                        f"{'Power BI' if has_tableau else 'Tableau'} to cover both tool ecosystems.")

    # Top prioritized actions (dedup across fields), most impactful first.
    top_actions: list[str] = []
    seen_proj = set()
    if "IT Audit / Tech Risk" in focus:
        top_actions.append("Build the ITGC mini-review project — it directly evidences your "
                           "#1 target (IT audit) which your résumé currently can't prove.")
    for pf in per_field:
        for pr in pf["projects"]:
            if pr not in seen_proj:
                seen_proj.add(pr)
    # One cert pick per focus field (skip ones marked 'have it'/ongoing).
    for pf in per_field[:3]:
        for name, why, effort in pf["certifications"]:
            if effort not in ("have it", "ongoing"):
                top_actions.append(f"Start **{name}** for {pf['field']} — {why}")
                break
    top_actions.append("Maintain field-specific résumé variants (below) and tailor per JD with "
                       "`python -m job_bot.generate --file <jd>.txt`.")

    return {
        "have": sorted(_pretty(s) for s in have),
        "focus_fields": focus,
        "target_fields": target_fields,
        "per_field": per_field,
        "insights": insights,
        "top_actions": top_actions,
    }


def main() -> None:
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    plan = build_plan()
    print("\nGROWTH PLAN — focus fields:", ", ".join(plan["focus_fields"]), "\n")
    print("Top actions:")
    for i, a in enumerate(plan["top_actions"], 1):
        print(f"  {i}. {a}")
    for pf in plan["per_field"]:
        tag = " (stated target)" if pf["is_stated_target"] else ""
        print(f"\n■ {pf['field']}{tag} — {pf['applied_count']} applications")
        print("   strengths:", ", ".join(pf["strengths"]) or "—")
        print("   gaps:", ", ".join(pf["gaps"]) or "none")
        if pf["projects"]:
            print("   projects:")
            for pr in pf["projects"]:
                print(f"     · {pr}")
        print("   certs:")
        for name, why, effort in pf["certifications"]:
            print(f"     · {name} [{effort}]")
    if plan["insights"]:
        print("\nInsights:")
        for i in plan["insights"]:
            print("  -", i.replace("**", ""))


if __name__ == "__main__":
    main()
