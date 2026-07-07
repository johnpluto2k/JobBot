"""Curated skill/keyword ontology for JD parsing and reverse ATS scoring.

Keeping this explicit (rather than relying on heavy NLP models) makes keyword
extraction deterministic, debuggable, and fast — and it runs anywhere. Each
canonical skill maps to a list of aliases/synonyms that may appear in a JD or
resume. Matching is case-insensitive on word boundaries.
"""

from __future__ import annotations

# canonical skill -> aliases (all lowercase). The canonical form is what we
# report; any alias hit counts as the canonical skill being present.
SKILL_ALIASES: dict[str, list[str]] = {
    # --- data / technical ---
    "sql": ["sql", "structured query language", "t-sql", "pl/sql", "mysql", "postgresql", "postgres"],
    "python": ["python", "pandas", "numpy"],
    "r": ["r programming", " r,", " r ", "rstudio"],
    "excel": ["excel", "ms excel", "microsoft excel", "spreadsheets", "pivot tables", "vlookup"],
    "power bi": ["power bi", "powerbi"],
    "tableau": ["tableau"],
    "data analysis": ["data analysis", "data analytics", "analytics", "analyze data", "data-driven"],
    "data visualization": ["data visualization", "dashboards", "dashboard", "reporting"],
    "etl": ["etl", "data pipeline", "data pipelines"],
    "vba": ["vba", "macros"],
    "alteryx": ["alteryx"],
    "sap": ["sap", "erp"],
    "javascript": ["javascript", "js", "node.js", "node", "react"],
    "statistics": ["statistics", "statistical", "regression"],
    "machine learning": ["machine learning", "ml", "predictive model"],
    # --- audit / risk / accounting ---
    "auditing": ["audit", "auditing", "internal audit", "external audit"],
    "it audit": ["it audit", "technology risk", "it risk", "itgc", "sox itgc"],
    "internal controls": ["internal controls", "internal control", "controls testing", "control testing"],
    "sox": ["sox", "sarbanes-oxley", "sarbanes oxley"],
    "risk management": ["risk management", "risk assessment", "enterprise risk", "operational risk"],
    "compliance": ["compliance", "regulatory", "regulatory compliance"],
    "gaap": ["gaap", "us gaap", "ifrs"],
    "financial reporting": ["financial reporting", "financial statements", "reporting"],
    "financial analysis": ["financial analysis", "financial modeling", "valuation", "dcf"],
    "fp&a": ["fp&a", "fpa", "financial planning", "budgeting", "forecasting"],
    "accounting": ["accounting", "accounts payable", "accounts receivable", "general ledger", "reconciliation"],
    "tax": ["tax", "taxation", "tax preparation", "vita", "tce"],
    "cpa": ["cpa", "certified public accountant", "cpa eligible", "cpa eligibility"],
    "cybersecurity": ["cybersecurity", "information security", "infosec", "security controls"],
    # --- soft / professional ---
    "stakeholder management": ["stakeholder", "stakeholder management", "client service", "client-facing"],
    "communication": ["communication", "written and verbal", "presentation", "presenting"],
    "leadership": ["leadership", "led", "mentoring", "mentored", "supervised"],
    "collaboration": ["collaboration", "cross-functional", "teamwork", "team player"],
    "problem solving": ["problem solving", "problem-solving", "critical thinking"],
    "project management": ["project management", "project manager", "agile", "scrum"],
    "attention to detail": ["attention to detail", "detail-oriented", "detail oriented", "accuracy"],
}

# Role-type classification: type -> skills that signal it. Used to label the JD.
ROLE_TYPE_SIGNALS: dict[str, list[str]] = {
    "IT Audit / Technology Risk": ["it audit", "auditing", "internal controls", "sox",
                                    "cybersecurity", "risk management", "compliance"],
    "Audit / Assurance": ["auditing", "internal controls", "gaap", "financial reporting",
                           "cpa", "accounting"],
    "Data Analytics": ["data analysis", "sql", "tableau", "power bi", "python",
                       "data visualization", "statistics"],
    "FP&A / Corporate Finance": ["fp&a", "financial analysis", "financial reporting",
                                 "accounting", "excel"],
    "FinTech": ["python", "sql", "javascript", "risk management", "data analysis", "compliance"],
    "Tax": ["tax", "accounting", "compliance", "cpa"],
    "Software Engineering": ["javascript", "python", "machine learning", "etl"],
}

# Geographic market tiers (from the master plan).
MARKET_TIERS: dict[str, dict] = {
    "Tier 1 — DMV": {
        "tier": 1,
        "states": ["dc", "d.c.", "washington, dc", "maryland", "md", "virginia", "va", "dmv"],
        "cities": ["washington", "arlington", "mclean", "tysons", "bethesda", "rockville",
                   "college park", "baltimore", "reston", "alexandria", "richmond"],
    },
    "Tier 2 — Major Market": {
        "tier": 2,
        "states": ["ny", "new york", "ca", "california", "il", "illinois", "ma", "massachusetts"],
        "cities": ["new york", "nyc", "manhattan", "san francisco", "sf", "chicago", "boston"],
    },
    "Tier 3 — Relocation": {
        "tier": 3,
        "states": ["wa", "washington state"],
        "cities": ["los angeles", "la", "san diego", "seattle"],
    },
}

# Company -> ATS platform (from the master plan's hiring-process intelligence).
COMPANY_ATS: dict[str, str] = {
    "deloitte": "Workday",
    "ey": "Workday",
    "ernst & young": "Workday",
    "kpmg": "Workday",
    "pwc": "Taleo",
    "pricewaterhousecoopers": "Taleo",
    "alvarez & marsal": "iCIMS",
    "cohnreznick": "iCIMS",
    "stripe": "Greenhouse",
    "plaid": "Greenhouse",
    "robinhood": "Greenhouse",
    "block": "Greenhouse",
    "xometry": "Lever",
}

# Known employers -> canonical display name (for company extraction from JDs).
KNOWN_COMPANIES: dict[str, str] = {
    "deloitte": "Deloitte", "pwc": "PwC", "pricewaterhousecoopers": "PwC",
    "ernst & young": "EY", "ernst and young": "EY", "ey": "EY", "kpmg": "KPMG",
    "goldman sachs": "Goldman Sachs", "jpmorgan": "JPMorgan", "j.p. morgan": "JPMorgan",
    "morgan stanley": "Morgan Stanley", "booz allen": "Booz Allen Hamilton",
    "accenture": "Accenture", "protiviti": "Protiviti", "grant thornton": "Grant Thornton",
    "rsm": "RSM", "bdo": "BDO", "cohnreznick": "CohnReznick",
    "alvarez & marsal": "Alvarez & Marsal", "capital one": "Capital One",
    "fannie mae": "Fannie Mae", "freddie mac": "Freddie Mac",
    "google": "Google", "meta": "Meta", "microsoft": "Microsoft", "amazon": "Amazon",
    "apple": "Apple", "netflix": "Netflix", "nvidia": "NVIDIA",
    "stripe": "Stripe", "plaid": "Plaid", "robinhood": "Robinhood", "block": "Block",
    "xometry": "Xometry",
    # Mid-tier / regional accounting + firms John actually applied to (from his inbox)
    "rsm": "RSM", "andersen": "Andersen", "andersentax": "Andersen",
    "eisneramper": "EisnerAmper", "cohnreznick": "CohnReznick", "baker tilly": "Baker Tilly",
    "bakertilly": "Baker Tilly", "cherry bekaert": "Cherry Bekaert", "cherrybekaert": "Cherry Bekaert",
    "cla": "CliftonLarsonAllen", "cliftonlarsonallen": "CliftonLarsonAllen",
    "uhy": "UHY", "cerity partners": "Cerity Partners", "ceritypartners": "Cerity Partners",
    "tighe & bond": "Tighe & Bond", "tighebond": "Tighe & Bond", "tighe and bond": "Tighe & Bond",
    "alvarez and marsal": "Alvarez & Marsal",
    # Corporates / banks John applied to
    "citi": "Citi", "citigroup": "Citi", "wells fargo": "Wells Fargo", "raytheon": "Raytheon",
    "rtx": "Raytheon", "nissan": "Nissan", "insulet": "Insulet", "comcast": "Comcast",
    "pepsico": "PepsiCo", "federal reserve": "Federal Reserve Bank",
    "american bankers association": "American Bankers Association",
    "enterprise bank": "Enterprise Bank & Trust", "dun & bradstreet": "Dun & Bradstreet",
    "dun and bradstreet": "Dun & Bradstreet", "eaton": "Eaton",
}

# Words that introduce required vs preferred qualification blocks.
REQUIRED_MARKERS = ["required", "requirements", "qualifications", "must have", "what you'll need",
                    "minimum qualifications", "basic qualifications", "you have", "you bring"]
PREFERRED_MARKERS = ["preferred", "nice to have", "bonus", "plus", "desired", "a plus",
                     "preferred qualifications"]


def all_aliases() -> list[tuple[str, str]]:
    """Flatten to (alias, canonical) pairs sorted longest-first so multi-word
    aliases match before their substrings."""
    pairs = [(alias, canon) for canon, aliases in SKILL_ALIASES.items() for alias in aliases]
    return sorted(pairs, key=lambda p: len(p[0]), reverse=True)
