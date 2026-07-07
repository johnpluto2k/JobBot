"""Phase 7: curated interview question bank by type and firm.

Question types (from the master plan): behavioral, fit, technical, case,
hirevue, curveball, your-questions.
"""

from __future__ import annotations

from .interview_models import Question

Q = Question

QUESTION_BANK: list[Question] = [
    # --- behavioral (STAR+) ---
    Q(text="Tell me about a time you led a team through a difficult situation.",
      qtype="behavioral", competency="Leadership", firm_types=["all"]),
    Q(text="Describe a time you used data to solve a problem.",
      qtype="behavioral", competency="Analytical / Problem Solving", firm_types=["tech", "fintech", "big4"]),
    Q(text="Tell me about a time you caught an error others missed.",
      qtype="behavioral", competency="Attention to Detail / Compliance", firm_types=["big4", "ib", "corporate"]),
    Q(text="Give an example of managing competing priorities under a deadline.",
      qtype="behavioral", competency="Ownership / Initiative", firm_types=["all"]),
    Q(text="Tell me about a time you worked with a difficult teammate or stakeholder.",
      qtype="behavioral", competency="Communication / Stakeholders", firm_types=["all"]),
    Q(text="Describe a project you built from scratch.",
      qtype="behavioral", competency="Technical / Building", firm_types=["tech", "fintech"]),

    # --- fit / motivational ---
    Q(text="Walk me through your resume.", qtype="fit", firm_types=["all"],
      hint="90 seconds: education → most relevant experience → why this role now."),
    Q(text="Why this firm, and why this role?", qtype="fit", firm_types=["all"],
      hint="Tie a specific firm value/team to your finance+tech positioning."),
    Q(text="Why audit / technology risk over a pure finance or pure tech path?",
      qtype="fit", firm_types=["big4"], hint="Use your Accounting + Information Science double major."),
    Q(text="Where do you see yourself in 3–5 years?", qtype="fit", firm_types=["all"]),

    # --- technical ---
    Q(text="Walk me through the three financial statements and how they link.",
      qtype="technical", competency="Financial Acumen", firm_types=["ib", "big4", "corporate"]),
    Q(text="What is an ITGC, and why does it matter for SOX?",
      qtype="technical", firm_types=["big4"], hint="IT general controls: access, change mgmt, operations."),
    Q(text="Write a SQL query to find the top 5 customers by total spend.",
      qtype="technical", firm_types=["tech", "fintech"], hint="GROUP BY, ORDER BY, LIMIT."),
    Q(text="How would you assess the financial risk of an AI system rollout?",
      qtype="technical", firm_types=["big4", "fintech"], hint="You did this in the KPMG case competition."),
    Q(text="What's the difference between accrual and cash accounting?",
      qtype="technical", competency="Financial Acumen", firm_types=["big4", "corporate"]),

    # --- case ---
    Q(text="Estimate the number of coffee shops in Washington, DC.",
      qtype="case", firm_types=["consulting", "big4"], hint="Population → per-capita demand → outlets."),
    Q(text="A client's profits are falling despite rising revenue — how do you investigate?",
      qtype="case", firm_types=["consulting", "big4"], hint="Profit = Rev − Cost; segment both."),

    # --- hirevue (one-way video) ---
    Q(text="In 2 minutes: tell us about yourself and why this role.",
      qtype="hirevue", firm_types=["big4", "ib"], hint="Tight, structured, confident; practice on camera."),
    Q(text="Describe a time you showed leadership. (2-minute recorded answer)",
      qtype="hirevue", firm_types=["big4"], hint="Front-load the result; AI scores keywords + structure."),

    # --- curveball ---
    Q(text="Sell me this pen.", qtype="curveball", firm_types=["ib", "tech"],
      hint="Discover need → tie features to it → close."),
    Q(text="What would you do with $1M to improve this company?",
      qtype="curveball", firm_types=["tech", "fintech"]),

    # --- your questions (to ask them) ---
    Q(text="What does success look like in this role in the first 6 months?",
      qtype="questions", firm_types=["all"]),
    Q(text="How is the team using data/automation to improve how it works?",
      qtype="questions", firm_types=["tech", "fintech", "big4"]),
    Q(text="What's the path from this role to the next level here?",
      qtype="questions", firm_types=["all"]),
]

FIRM_NOTES: dict[str, str] = {
    "big4": "Big 4: STAR+ with explicit reflection; expect HireVue + Super Day; 'why this firm' matters.",
    "ib": "Investment banking: technicals are gating (3-statement, DCF); expect rapid-fire Superday.",
    "tech": "Tech: SQL/coding screen + take-home; emphasize impact and ownership.",
    "fintech": "FinTech: conversational, culture-fit + a case/take-home; faster process.",
    "corporate": "Fortune 500: behavioral + situational; panel loop; RSUs and more negotiation room.",
    "consulting": "Consulting: case frameworks (profitability, market sizing, entry) + behavioral.",
}


def filter_questions(qtype: str | None = None, firm: str | None = None) -> list[Question]:
    out = QUESTION_BANK
    if qtype:
        out = [q for q in out if q.qtype == qtype]
    if firm:
        out = [q for q in out if "all" in q.firm_types or firm in q.firm_types]
    return out
