#!/usr/bin/env python3
"""Seed a broad, multi-lane target-company list into the company tracker.

Context: as of 2026-08-26 the tracker held 55 companies, 53 of whose field tags were
Audit/Tax/Internal Audit/FP&A — 1 IT Audit, 0 Data & Analytics, ~4 tech. That is an
accounting-firm list, not a job search across John's actual skill set (Accounting +
Information Science; Python/SQL/R; ships full-stack software).

This adds the missing lanes: tech, fintech, GRC/audit-tech, tech consulting, strategy
consulting, govcon, data & analytics, DMV mid-size, and startups — plus the mid-tier and
federal-audit accounting firms that were missing.

Idempotent: uses companies.get_or_create(), so re-running never duplicates and never
overwrites the 55 already there.

Usage:  python scripts/seed_broad_targets.py [--dry-run]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from job_bot import companies  # noqa: E402

# fields taxonomy — extends the existing one with the lanes John asked for
AUD = "Audit & Assurance"
ITA = "IT Audit / Tech Risk"
RSK = "Risk & Compliance"
TAX = "Tax"
FPA = "Finance / FP&A"
DAT = "Data & Analytics"
BA = "Business Analyst"
TCON = "Tech Consulting"
CON = "Consulting"
SWE = "Software & Engineering"

# (name, tier, [fields], region, note)
TARGETS = [
    # ---------------- BIG TECH — finance / BA / data / internal-audit functions ----
    ("Google", "big-tech", [FPA, BA, DAT], "Nat'l + DC", "Business Undergraduate Intern ~Sept; 3 apps/30 days"),
    ("Microsoft", "big-tech", [FPA, BA, DAT], "Nat'l + DC", "Finance rotation + BA internships"),
    ("Apple", "big-tech", [FPA, DAT], "Nat'l", ""),
    ("Meta", "big-tech", [FPA, BA, DAT], "Nat'l + DC", ""),
    ("Salesforce", "big-tech", [FPA, BA, DAT], "Nat'l", "Owns Tableau"),
    ("Adobe", "big-tech", [FPA, DAT], "Nat'l", ""),
    ("Oracle", "big-tech", [FPA, BA, DAT], "Nat'l", ""),
    ("IBM", "big-tech", [TCON, BA, DAT], "Nat'l + DC", "Consulting arm hires heavily in DMV"),
    ("Intuit", "big-tech", [FPA, DAT, TAX], "Nat'l", "Tax + accounting product — strong narrative fit"),
    ("Workday", "big-tech", [FPA, BA], "Nat'l", "Finance/HR software; ATS John already knows"),
    ("ServiceNow", "big-tech", [BA, RSK], "Nat'l + DC", "GRC module — audit-adjacent"),
    ("SAP", "big-tech", [FPA, BA], "Nat'l", ""),
    ("Cisco", "big-tech", [FPA, DAT], "Nat'l", ""),
    ("Dell Technologies", "big-tech", [FPA, DAT], "Nat'l", ""),
    ("NVIDIA", "big-tech", [FPA, DAT], "Nat'l", ""),
    ("Amazon", "big-tech", [FPA, BA, DAT], "Nat'l + HQ2 Arlington", "ALREADY TRACKED — HQ2 is in Arlington"),
    ("Uber", "big-tech", [FPA, DAT], "Nat'l", ""),
    ("Airbnb", "big-tech", [FPA, DAT], "Nat'l", ""),
    ("Netflix", "big-tech", [FPA, DAT], "Nat'l", ""),
    ("Atlassian", "big-tech", [BA, DAT], "Remote-friendly", ""),
    ("Datadog", "big-tech", [FPA, DAT], "NYC", ""),
    ("Snowflake", "big-tech", [DAT, FPA], "Nat'l", ""),
    ("Databricks", "big-tech", [DAT], "Nat'l", ""),
    ("Palantir", "big-tech", [DAT, BA], "DC + Denver", "Heavy federal/DC presence"),

    # ---------------- GRC / AUDIT-TECH — the sharpest fit for his exact combo -----
    ("AuditBoard", "grc-tech", [ITA, AUD, RSK], "Remote/CA", "Audit software — accounting + tech in one"),
    ("Vanta", "grc-tech", [ITA, RSK], "Remote/SF", "SOC 2 compliance automation"),
    ("Drata", "grc-tech", [ITA, RSK], "Remote/SD", "Compliance automation"),
    ("Workiva", "grc-tech", [AUD, RSK, FPA], "Remote/Ames", "Financial reporting + SOX platform"),
    ("LogicGate", "grc-tech", [RSK, ITA], "Chicago/Remote", "Risk Cloud GRC"),
    ("OneTrust", "grc-tech", [RSK, ITA], "Atlanta", "Privacy/GRC"),
    ("Hyperproof", "grc-tech", [ITA, RSK], "Remote/Seattle", ""),
    ("Secureframe", "grc-tech", [ITA, RSK], "Remote/SF", ""),
    ("Diligent", "grc-tech", [RSK, AUD], "NYC", "Board governance + GRC"),
    ("MetricStream", "grc-tech", [RSK, ITA], "Remote", ""),
    ("FloQast", "grc-tech", [AUD, FPA], "Remote/LA", "Accounting close automation"),
    ("BlackLine", "grc-tech", [AUD, FPA], "Remote/LA", "Financial close software"),
    ("Numeric", "startup", [AUD, FPA], "SF/NYC", "AI close software; small, early"),
    ("Puzzle", "startup", [AUD, FPA], "Remote/SF", "AI-native accounting"),
    ("Trullion", "startup", [AUD], "NYC", "AI audit/lease accounting"),

    # ---------------- FINTECH ----------------------------------------------------
    ("Capital One", "fintech", [DAT, BA, RSK, FPA], "McLean VA", "HUGE DMV employer; strong analyst programs"),
    ("Stripe", "fintech", [FPA, DAT], "Remote/SF", "Already a target firm in profile"),
    ("Plaid", "fintech", [FPA, DAT], "Remote/SF", "He built a Plaid integration — real talking point"),
    ("Block", "fintech", [FPA, DAT], "Remote", ""),
    ("Coinbase", "fintech", [FPA, RSK], "Remote", ""),
    ("Chime", "fintech", [FPA, DAT], "Remote/SF", ""),
    ("Brex", "fintech", [FPA, DAT], "Remote/SF", ""),
    ("Ramp", "fintech", [FPA, DAT], "NYC", ""),
    ("Affirm", "fintech", [FPA, RSK], "Remote", ""),
    ("SoFi", "fintech", [FPA, RSK], "Remote", ""),
    ("Marqeta", "fintech", [FPA], "Remote", ""),
    ("PayPal", "fintech", [FPA, RSK, DAT], "Nat'l", ""),
    ("Fiserv", "fintech", [FPA, ITA], "Nat'l", ""),
    ("FIS", "fintech", [FPA, ITA], "Nat'l", ""),
    ("Fannie Mae", "financial-services", [ITA, RSK, FPA, DAT], "Washington DC", "Big DMV; strong internal audit"),
    ("Freddie Mac", "financial-services", [ITA, RSK, FPA, DAT], "McLean VA", "Big DMV; strong internal audit"),

    # ---------------- TECH CONSULTING / SYSTEMS INTEGRATION ----------------------
    ("Accenture", "tech-consulting", [TCON, ITA, BA, DAT], "Nat'l + DC", "Tech consulting at scale"),
    ("Accenture Federal Services", "tech-consulting", [TCON, ITA, BA], "Arlington VA", "Federal arm, DMV-based"),
    ("Slalom", "tech-consulting", [TCON, BA, DAT], "DC + Nat'l", ""),
    ("Booz Allen Hamilton", "tech-consulting", [TCON, ITA, DAT, RSK], "McLean VA", "Largest DMV consulting employer"),
    ("Guidehouse", "tech-consulting", [CON, ITA, RSK, FPA], "McLean VA", "Spun out of PwC Public Sector"),
    ("ICF", "tech-consulting", [CON, DAT, BA], "Reston VA", ""),
    ("LMI", "tech-consulting", [CON, DAT], "Tysons VA", ""),
    ("MITRE", "tech-consulting", [TCON, DAT, RSK], "McLean VA", "FFRDC; research-flavored"),
    ("Capgemini", "tech-consulting", [TCON, BA], "Nat'l", ""),
    ("Cognizant", "tech-consulting", [TCON, BA], "Nat'l", ""),
    ("EPAM Systems", "tech-consulting", [TCON, SWE], "Nat'l", ""),
    ("Thoughtworks", "tech-consulting", [TCON, SWE], "Nat'l", ""),
    ("West Monroe", "tech-consulting", [TCON, BA, DAT], "Chicago/DC", ""),
    ("Huron Consulting", "tech-consulting", [CON, BA], "Chicago/Nat'l", ""),
    ("Gartner", "tech-consulting", [DAT, BA, CON], "Arlington VA", "Research/advisory; big Arlington office"),
    ("Forrester", "tech-consulting", [DAT, BA], "Boston/Remote", ""),

    # ---------------- STRATEGY / MANAGEMENT CONSULTING --------------------------
    ("McKinsey & Company", "strategy-consulting", [CON, DAT], "DC + Nat'l", ""),
    ("Boston Consulting Group", "strategy-consulting", [CON, DAT], "DC + Nat'l", ""),
    ("Bain & Company", "strategy-consulting", [CON, DAT], "DC + Nat'l", ""),
    ("Oliver Wyman", "strategy-consulting", [CON, RSK], "DC/NYC", ""),
    ("L.E.K. Consulting", "strategy-consulting", [CON], "Nat'l", ""),
    ("Kearney", "strategy-consulting", [CON], "Nat'l", ""),
    ("FTI Consulting", "strategy-consulting", [CON, AUD, RSK], "Washington DC", "Forensic/disputes; DC HQ"),
    ("Charles River Associates", "strategy-consulting", [CON, DAT], "DC/Boston", ""),
    ("Analysis Group", "strategy-consulting", [CON, DAT], "DC/Boston", ""),
    ("Berkeley Research Group", "strategy-consulting", [CON, AUD], "DC", ""),
    ("Ankura", "strategy-consulting", [CON, RSK], "Washington DC", ""),
    ("StoneTurn", "strategy-consulting", [AUD, RSK], "DC/Boston", "Forensic accounting + compliance"),
    ("Exponent", "strategy-consulting", [CON, DAT], "Nat'l", ""),

    # ---------------- GOVCON / DEFENSE (DMV core) --------------------------------
    ("Leidos", "govcon", [ITA, DAT, FPA], "Reston VA", ""),
    ("CACI International", "govcon", [ITA, DAT, FPA], "Reston VA", ""),
    ("SAIC", "govcon", [ITA, DAT, FPA], "Reston VA", ""),
    ("Peraton", "govcon", [ITA, DAT], "Herndon VA", ""),
    ("General Dynamics IT", "govcon", [ITA, DAT], "Falls Church VA", ""),
    ("Northrop Grumman", "govcon", [FPA, ITA], "Falls Church VA", ""),
    ("Lockheed Martin", "govcon", [FPA, ITA, DAT], "Bethesda MD", "HQ in Bethesda"),
    ("Amentum", "govcon", [FPA, ITA], "Chantilly VA", ""),
    ("Maximus", "govcon", [FPA, DAT, BA], "Tysons VA", ""),
    ("Noblis", "govcon", [TCON, DAT], "Reston VA", ""),
    ("Systems Planning and Analysis", "govcon", [DAT, CON], "Alexandria VA", ""),

    # ---------------- DATA & ANALYTICS / INFO SERVICES ---------------------------
    ("Moody's", "data-analytics", [DAT, RSK, FPA], "NYC", ""),
    ("S&P Global", "data-analytics", [DAT, FPA], "NYC", ""),
    ("MSCI", "data-analytics", [DAT, RSK], "NYC", ""),
    ("FactSet", "data-analytics", [DAT, FPA], "NYC/CT", ""),
    ("Morningstar", "data-analytics", [DAT, FPA], "Chicago", ""),
    ("Verisk", "data-analytics", [DAT, RSK], "NJ/Remote", ""),
    ("IQVIA", "data-analytics", [DAT], "Nat'l", ""),
    ("Experian", "data-analytics", [DAT, RSK], "Nat'l", ""),
    ("Equifax", "data-analytics", [DAT, RSK], "Atlanta", ""),
    ("TransUnion", "data-analytics", [DAT, RSK], "Chicago", ""),
    ("CoStar Group", "data-analytics", [DAT, BA], "Washington DC", "DC HQ; real-estate data"),
    ("Elder Research", "data-analytics", [DAT], "Charlottesville VA", "Boutique data science shop"),
    ("Summit Consulting", "data-analytics", [DAT, CON], "Washington DC", "Small DC econometrics/analytics firm"),
    ("Fors Marsh", "data-analytics", [DAT, CON], "Arlington VA", "Applied research/analytics"),
    ("EAB", "data-analytics", [DAT, BA, CON], "Washington DC", "Education research/advisory"),
    ("2U", "data-analytics", [DAT, BA], "Lanham MD", ""),

    # ---------------- DMV TECH / MID-SIZE ----------------------------------------
    ("Appian", "dmv-tech", [BA, SWE, TCON], "McLean VA", "Low-code platform; local"),
    ("Cvent", "dmv-tech", [BA, DAT, FPA], "Tysons VA", ""),
    ("ID.me", "dmv-tech", [BA, RSK], "McLean VA", ""),
    ("Expel", "dmv-tech", [ITA, RSK], "Herndon VA", "Managed security — cyber/audit adjacent"),
    ("Virtru", "dmv-tech", [ITA, RSK], "Washington DC", "Data encryption; small"),
    ("ThreatConnect", "dmv-tech", [ITA, RSK], "Arlington VA", "Threat intel; small"),
    ("Aledade", "dmv-tech", [DAT, FPA], "Bethesda MD", "Healthcare analytics"),
    ("Arcadia", "dmv-tech", [DAT], "Washington DC", "Energy data"),
    ("Blackbaud", "dmv-tech", [BA, FPA], "Remote/Charleston", "Nonprofit fintech"),
    ("Danaher", "dmv-tech", [FPA, AUD], "Washington DC", "DC HQ; strong finance leadership program"),
    ("Marriott International", "dmv-tech", [FPA, AUD, DAT], "Bethesda MD", "Big Bethesda finance org"),
    ("Under Armour", "dmv-tech", [FPA, AUD], "Baltimore MD", ""),
    ("GEICO", "dmv-tech", [DAT, FPA, ITA], "Chevy Chase MD", ""),

    # ---------------- FEDERAL FINANCIAL AUDIT (DMV, very on-target for IT audit) --
    ("Kearney & Company", "federal-audit", [AUD, ITA], "Alexandria VA", "Federal financial-statement audit specialist"),
    ("Sikich", "federal-audit", [AUD, ITA], "Alexandria VA", "Absorbed Cotton & Company (federal audit)"),
    ("Williams Adley", "federal-audit", [AUD, ITA], "Washington DC", "Small federal audit firm"),
    ("Regis & Associates", "federal-audit", [AUD, ITA], "Washington DC", "Small federal audit firm"),
    ("Brown & Company CPAs", "federal-audit", [AUD, ITA], "Largo MD", "Small federal audit firm"),
    ("Allmond & Company", "federal-audit", [AUD], "Landover MD", "Small federal audit firm"),

    # ---------------- MID-TIER / REGIONAL ACCOUNTING (not yet tracked) ------------
    ("Aprio", "mid-tier-accounting", [AUD, TAX], "Bethesda MD", "Absorbed Aronson LLC"),
    ("Armanino", "mid-tier-accounting", [AUD, TAX, ITA], "Nat'l", "Strong tech-consulting practice"),
    ("Wipfli", "mid-tier-accounting", [AUD, TAX], "Nat'l", ""),
    ("Plante Moran", "mid-tier-accounting", [AUD, TAX], "Midwest", ""),
    ("Moss Adams", "mid-tier-accounting", [AUD, TAX], "West", ""),
    ("Forvis Mazars", "mid-tier-accounting", [AUD, TAX, ITA], "Nat'l", "Formerly FORVIS / Dixon Hughes Goodman"),
    ("Withum", "mid-tier-accounting", [AUD, TAX], "NJ/DC", ""),
    ("Marcum", "mid-tier-accounting", [AUD, TAX], "Nat'l", ""),
    ("PBMares", "regional-accounting", [AUD, TAX], "Virginia", ""),
    ("GRF CPAs & Advisors", "regional-accounting", [AUD, TAX], "Bethesda MD", "Nonprofit audit niche"),
    ("Councilor, Buchanan & Mitchell", "regional-accounting", [AUD, TAX], "Bethesda MD", ""),
    ("Rubino & Company", "regional-accounting", [AUD, TAX], "Bethesda MD", ""),
    ("Halt, Buzas & Powell", "regional-accounting", [AUD, TAX], "Alexandria VA", ""),
    ("Snyder Cohn", "regional-accounting", [AUD, TAX], "North Bethesda MD", ""),

    # ---------------- STARTUPS / HIGH-GROWTH (non-GRC) ---------------------------
    ("Rippling", "startup", [FPA, BA], "Remote/SF", ""),
    ("Deel", "startup", [FPA, BA], "Remote", ""),
    ("Gusto", "startup", [FPA, BA], "Remote/SF", ""),
    ("Mercury", "startup", [FPA, RSK], "Remote/SF", "Banking for startups"),
    ("Pilot", "startup", [AUD, FPA], "Remote/SF", "Outsourced accounting — direct fit"),
]


def main(dry_run: bool = False) -> None:
    created = existing = 0
    by_tier: dict[str, int] = {}
    for name, tier, fields, region, note in TARGETS:
        by_tier[tier] = by_tier.get(tier, 0) + 1
        if dry_run:
            continue
        _, was_created = companies.get_or_create(
            name,
            tier=tier,
            target_fields=fields,
            notes=(f"[{region}] {note}".strip() if note else f"[{region}]"),
        )
        created += was_created
        existing += (not was_created)

    print(f"targets in list : {len(TARGETS)}")
    for t, n in sorted(by_tier.items(), key=lambda kv: -kv[1]):
        print(f"  {t:24s} {n}")
    if dry_run:
        print("\n(dry run — nothing written)")
    else:
        print(f"\nnewly added     : {created}")
        print(f"already present : {existing}")


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
