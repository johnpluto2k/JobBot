"""A fictional job search, so the dashboard has something to show.

``python -m job_bot demo`` points the app at ``demo_data/`` (never your real
``data/``), fills it with the search of an invented candidate, and starts the
dashboard. Nothing here is real: the person, the companies (all on the reserved
``.example`` domain) and every email are made up.

The data goes in through the same functions the app uses day to day
(``intake.log_job``, ``inbox.record_email``, ``offers.log_offer`` ...), so what
you see is what the real classifier and funnel produce, not a mocked screen.
Dates are relative to today so the demo never looks stale.

The caller must set ``JOB_BOT_OUTPUT_DIR`` before any ``job_bot`` module is
imported; ``job_bot.__main__`` does that. ``seed()`` refuses to write anywhere
that is not a demo directory.
"""

from __future__ import annotations

import json
import zlib
from datetime import date, datetime, timedelta
from pathlib import Path

DEMO_DIR_NAME = "demo_data"
MARKER = ".demo"

PROFILE = {
    "personal": {
        "name": "Sam Rivera",
        "email": "sam.rivera@mail.example",
        "phone": "555-0100",
        "location": "Chicago, IL",
        "linkedin": "linkedin.com/in/sam-rivera-example",
        "github": "github.com/sam-rivera-example",
        "headline": "Data analyst, graduating May 2027",
    },
    "education": [{
        "school": "Lakeshore State University",
        "degree": "B.S. Statistics",
        "major": "Statistics",
        "secondary_major": "Computer Science",
        "gpa": 3.6,
        "graduation_date": "May 2027",
        "relevant_coursework": ["Regression Analysis", "Databases", "Machine Learning",
                                "Data Visualization", "Algorithms"],
        "honors": ["Dean's List (4 semesters)"],
    }],
    "experience": [
        {
            "role": "Data Analyst Intern", "organization": "Harborview Health",
            "location": "Chicago, IL", "start_date": "Jun 2026", "end_date": "Aug 2026",
            "is_current": False,
            "bullets": [
                {"text": "Built a SQL and Python pipeline that cut weekly readmission reporting from 6 hours to 40 minutes",
                 "keyword_tags": ["SQL", "Python", "ETL"], "quantified": True, "strength_score": 0.9},
                {"text": "Designed a Tableau dashboard used by 30 nurse managers to track staffing against patient volume",
                 "keyword_tags": ["Tableau", "data visualization"], "quantified": True, "strength_score": 0.8},
                {"text": "Validated 1.2M claim records against source systems and documented 14 data quality rules",
                 "keyword_tags": ["data quality", "SQL"], "quantified": True, "strength_score": 0.7},
            ],
        },
        {
            "role": "Research Assistant", "organization": "Lakeshore State Urban Lab",
            "location": "Chicago, IL", "start_date": "Sep 2025", "end_date": "Present",
            "is_current": True,
            "bullets": [
                {"text": "Cleaned and merged 8 years of transit ridership data in pandas for a published commuting study",
                 "keyword_tags": ["Python", "pandas"], "quantified": True, "strength_score": 0.7},
                {"text": "Fit regression models in R to estimate the effect of fare changes on ridership",
                 "keyword_tags": ["R", "regression", "statistics"], "quantified": False, "strength_score": 0.6},
            ],
        },
        {
            "role": "Peer Tutor, Statistics", "organization": "Lakeshore State Learning Center",
            "location": "Chicago, IL", "start_date": "Jan 2025", "end_date": "May 2026",
            "is_current": False,
            "bullets": [
                {"text": "Tutored 45 students in introductory statistics across 3 semesters",
                 "keyword_tags": ["communication", "teaching"], "quantified": True, "strength_score": 0.5},
            ],
        },
    ],
    "leadership": [{
        "role": "Vice President", "organization": "Data Science Club",
        "location": "Chicago, IL", "start_date": "Aug 2025", "end_date": "Present",
        "bullets": [
            {"text": "Organized a 120-person datathon with 5 sponsoring employers",
             "keyword_tags": ["leadership", "event planning"], "quantified": True, "strength_score": 0.7},
        ],
        "competencies": ["Leadership", "Teamwork"],
    }],
    "projects": [
        {
            "name": "Bike-share demand forecast",
            "description": "Hourly demand model for a city bike-share system",
            "technologies": ["Python", "scikit-learn", "PostgreSQL"],
            "bullets": [
                {"text": "Trained a gradient-boosted model on 4M trips that beat the seasonal baseline by 18% MAE",
                 "keyword_tags": ["Python", "machine learning", "scikit-learn"], "quantified": True, "strength_score": 0.8},
            ],
            "url": "github.com/sam-rivera-example/bikeshare-forecast",
        },
        {
            "name": "Course-planner web app",
            "description": "Degree-requirement tracker used by classmates",
            "technologies": ["TypeScript", "React", "FastAPI"],
            "bullets": [
                {"text": "Shipped a React and FastAPI app that 200 students used to plan their final two years",
                 "keyword_tags": ["React", "TypeScript", "API"], "quantified": True, "strength_score": 0.7},
            ],
            "url": "github.com/sam-rivera-example/course-planner",
        },
    ],
    "skills": [
        {"category": "technical", "skills": ["Python", "SQL", "R", "Tableau", "pandas", "scikit-learn",
                                              "PostgreSQL", "Git", "Excel", "TypeScript"]},
        {"category": "analytical", "skills": ["Statistics", "Regression", "A/B Testing", "Data Visualization"]},
        {"category": "soft", "skills": ["Communication", "Teaching", "Project Management"]},
    ],
    "targets": {
        "target_roles": ["Data Analyst", "Business Intelligence Analyst", "Analytics Engineer"],
        "target_firms": ["Northwind", "Globex", "Initech"],
        "target_markets": ["Chicago, IL", "Remote"],
        "personas": ["analytics"],
    },
    "certifications": ["Google Data Analytics Certificate"],
    "summary": "Statistics and computer science student who turns messy operational data into "
               "dashboards and models people use.",
    "extraction_method": "demo",
    "schema_version": "1.0",
}


def demo_dir(project_root: Path) -> Path:
    return project_root / DEMO_DIR_NAME


def is_seeded(out_dir: Path) -> bool:
    return (out_dir / MARKER).exists() and (out_dir / "job_bot.db").exists()


def _ago(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


def _mail(days_ago: int, company: str, subject: str, body: str, *, local: str = "talent") -> None:
    from . import inbox

    domain = company.lower().replace(" ", "")
    inbox.record_email(
        f"{_ago(days_ago)}T14:05:00+00:00", f"{company} Recruiting <{local}@{domain}.example>",
        subject, body, gmail_id=f"demo-{domain}-{days_ago}-{zlib.crc32(subject.encode()) % 10_000}")


def seed(out_dir: Path, *, reset: bool = False) -> dict:
    """Fill `out_dir` with the demo search. Returns counts of what was written."""
    from . import companies, config, connections, db, intake, offers

    out_dir = Path(out_dir).resolve()
    if Path(config.OUTPUT_DIR).resolve() != out_dir or Path(db.DB_PATH).resolve().parent != out_dir:
        raise RuntimeError(
            "demo.seed() was called while the app points at a different data directory "
            f"({config.OUTPUT_DIR}). Start it with `python -m job_bot demo` so your real "
            "data cannot be touched.")
    if out_dir.exists() and any(out_dir.iterdir()) and not (out_dir / MARKER).exists():
        raise RuntimeError(f"{out_dir} holds data that was not created by the demo; refusing to write there.")

    if reset and out_dir.exists():
        for name in ("job_bot.db", "job_bot.db-wal", "job_bot.db-shm", "master_profile.json", MARKER):
            (out_dir / name).unlink(missing_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / MARKER).write_text("Fictional demo data written by job_bot.demo. Safe to delete.\n",
                                  encoding="utf-8")
    profile = {**PROFILE, "generated_at": datetime.now().isoformat(timespec="seconds")}
    config.PROFILE_JSON.write_text(json.dumps(profile, indent=2), encoding="utf-8")

    def job_url(company: str, slug: str) -> str:
        return f"https://careers.{company.lower()}.example/jobs/{slug}"

    # --- Applications the candidate logged after applying ----------------------
    logged = [
        # company, title, portal, days ago
        ("Northwind", "Data Analyst, Operations", "linkedin", 34),
        ("Northwind", "Business Intelligence Analyst", "linkedin", 20),
        ("Globex", "Associate Data Analyst", "greenhouse", 31),
        ("Initech", "Analytics Engineer I", "workday", 27),
        ("Hooli", "Product Analyst, New Grad", "greenhouse", 24),
        ("Vandelay", "Supply Chain Data Analyst", "indeed", 48),
        ("Bluepeak", "Junior Data Scientist", "handshake", 45),
        ("Lumina", "Marketing Analyst", "linkedin", 12),
        ("Wayfinder", "Data Analyst, Growth", "greenhouse", 6),
        ("Tessellate", "BI Developer", "other", 3),
    ]
    for company, title, portal, days in logged:
        slug = title.lower().replace(",", "").replace(" ", "-")
        intake.log_job(job_url(company, slug), company, title, portal=portal, applied_on=_ago(days))

    # --- What arrived in the inbox afterwards -----------------------------------
    def receipt(days: int, company: str, role: str) -> None:
        _mail(days, company, f"Thank you for applying to {company}",
              f"Hi Sam,\n\nThank you for applying for the {role} position at {company}. "
              "We have received your application and our team will review it.\n")

    receipt(34, "Northwind", "Data Analyst, Operations")
    receipt(20, "Northwind", "Business Intelligence Analyst")
    receipt(31, "Globex", "Associate Data Analyst")
    receipt(27, "Initech", "Analytics Engineer I")
    receipt(24, "Hooli", "Product Analyst, New Grad")
    receipt(48, "Vandelay", "Supply Chain Data Analyst")
    receipt(45, "Bluepeak", "Junior Data Scientist")
    receipt(12, "Lumina", "Marketing Analyst")
    receipt(6, "Wayfinder", "Data Analyst, Growth")
    # An application that was never logged by hand: the receipt alone tracks it.
    receipt(9, "Quillon", "Reporting Analyst")

    _mail(22, "Northwind", "Interview invitation: Data Analyst, Operations",
          "Hi Sam,\n\nWe would like to invite you to interview for the Data Analyst, Operations "
          "position. Please use the link below to schedule a 45-minute video interview with the "
          "hiring manager.\n")
    _mail(5, "Northwind", "Your offer from Northwind",
          "Hi Sam,\n\nWe are pleased to offer you the position of Data Analyst, Operations. "
          "Your offer letter is attached. Please respond by the date in the letter.\n")
    _mail(18, "Globex", "Next step: complete your online assessment",
          "Hi Sam,\n\nThank you for applying for the Associate Data Analyst position. As a next "
          "step, you are invited to complete our online assessment within 7 days.\n")
    _mail(8, "Globex", "Schedule your interview with Globex",
          "Hi Sam,\n\nCongratulations on passing the assessment. We would like to schedule a "
          "first-round interview for the Associate Data Analyst position next week.\n")
    _mail(14, "Initech", "Update on your application",
          "Hi Sam,\n\nThank you for your interest in the Analytics Engineer I position. "
          "Unfortunately, we have decided not to move forward with your application at this time.\n")
    _mail(2, "Lumina", "Quick question about your availability",
          "Hi Sam,\n\nI'm a recruiter on the analytics team at Lumina and I liked your bike-share "
          "project. Do you have 20 minutes this week for a call about the Marketing Analyst role?\n",
          local="jordan.lee")

    con = db.connect()
    try:
        # --- Interviews ---------------------------------------------------------
        when = (datetime.now() + timedelta(days=4)).replace(hour=15, minute=0, second=0, microsecond=0)
        con.executemany(
            "INSERT INTO interviews (company, role_title, round_name, firm_type, scheduled_at, status, notes) "
            "VALUES (?,?,?,?,?,?,?)",
            [("Globex", "Associate Data Analyst", "first round", "tech", when.isoformat(timespec="minutes"),
              "scheduled", "SQL screen, then a case on retention metrics"),
             ("Northwind", "Data Analyst, Operations", "final", "tech",
              (datetime.now() - timedelta(days=11)).isoformat(timespec="minutes"), "passed",
              "Panel with the ops analytics team")])

        # --- People the candidate knows ------------------------------------------
        for name, company, title, rel in [
            ("Priya Shah", "Northwind", "Senior Data Analyst", "alum"),
            ("Marcus Bell", "Globex", "University Recruiter", "recruiter"),
            ("Elena Petrova", "Hooli", "Product Analyst", "first_degree"),
            ("Tom Okafor", "Wayfinder", "Analytics Manager", "alum"),
            ("Dana Whitfield", "Lumina", "Marketing Analytics Lead", "second_degree"),
            ("Chris Nakamura", "Tessellate", "BI Engineer", "first_degree"),
        ]:
            connections.add_connection(con, name=name, company=company, title=title,
                                       relationship=rel, source="demo")

        # --- Outreach drafts (one follow-up is overdue) ---------------------------
        con.executemany(
            "INSERT INTO outreach (contact_name, company, role_title, kind, channel, message, status, "
            "sent_date, followup_date) VALUES (?,?,?,?,?,?,?,?,?)",
            [("Elena Petrova", "Hooli", "Product Analyst, New Grad", "follow_up", "linkedin",
              "Hi Elena, I applied for the new-grad Product Analyst role a few weeks ago and wanted "
              "to ask what the team looks for in a first analyst hire.", "drafted", None, _ago(2)),
             ("Tom Okafor", "Wayfinder", "Data Analyst, Growth", "referral_request", "linkedin",
              "Hi Tom, fellow Lakeshore State alum here. I just applied for the Growth analyst role "
              "and would value 15 minutes on how the team works.", "drafted", None, _ago(-3)),
             ("Priya Shah", "Northwind", "Data Analyst, Operations", "thank_you", "email",
              "Hi Priya, thank you for the introduction to the ops analytics team.", "sent",
              _ago(21), None)])

        # --- Fresh postings the watcher found (leads, not applications) -----------
        con.executemany(
            "INSERT OR IGNORE INTO jobs (title, company, location, site, url, date_posted, market_tier, "
            "tier_num, ats_score, priority, status, legit_score, legit_grade, recommendation, seniority) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,'new',?,?,?,?)",
            [("Data Analyst, Customer Insights", "Hooli", "Chicago, IL", "greenhouse",
              job_url("Hooli", "customer-insights-analyst"), _ago(2), "Tier 1", 1, 71.0, 86.0,
              92.0, "✅ Likely legit", "✅ Apply", "entry"),
             ("Analytics Engineer, New Grad", "Wayfinder", "Remote", "ashby",
              job_url("Wayfinder", "analytics-engineer-new-grad"), _ago(1), "Tier 2", 2, 64.0, 78.0,
              90.0, "✅ Likely legit", "✅ Apply", "entry"),
             ("Business Analyst", "Globex", "Chicago, IL", "greenhouse",
              job_url("Globex", "business-analyst"), _ago(4), "Tier 1", 1, 58.0, 70.0,
              88.0, "✅ Likely legit", "🟡 Maybe", "entry"),
             ("Senior Data Scientist", "Bluepeak", "Chicago, IL", "smartrecruiters",
              job_url("Bluepeak", "senior-data-scientist"), _ago(3), "Tier 2", 2, 41.0, 35.0,
              85.0, "✅ Likely legit", "⏭️ Skip", "senior"),
             ("Data Entry Analyst (Immediate Start)", "Brightpath Staffing", "Remote", "indeed",
              "https://jobs.brightpath-staffing.example/data-entry", _ago(1), "Tier 4", 4, 30.0, 12.0,
              38.0, "🚩 High risk", "🚩 Verify", "entry")])
        con.commit()
    finally:
        con.close()

    # --- Company tracker: tiers, fields and check-in dates -------------------------
    plan = {"Northwind": ("tier-1", -2), "Globex": ("tier-1", 0), "Hooli": ("tier-1", 3),
            "Wayfinder": ("tier-2", -1), "Lumina": ("tier-2", 5), "Initech": ("tier-2", 9)}
    due: list[tuple[str, int]] = []
    for c in companies.list_all():
        tier, due_in = plan.get(c["name"], ("other", 7))
        companies.update(c["id"], tier=tier, target_fields=["Data & Analytics"],
                         career_site_url=f"https://careers.{c['name'].lower()}.example")
        due.append((_ago(-due_in), c["id"]))
    con = db.connect()   # opened after the updates above: they use their own connection
    try:
        con.executemany("UPDATE companies SET next_check_due=? WHERE id=?", due)
        con.commit()
    finally:
        con.close()

    offers.log_offer("Northwind", "Data Analyst, Operations", base=78_000, bonus=5_000,
                     benefits_value=9_000, location="Chicago, IL", growth=4, fit=5,
                     deadline=_ago(-9), notes="Verbal offer confirmed by email; start in June.")

    from . import applications

    return {"dir": str(out_dir), **{k: v for k, v in applications.summary().items()
                                    if k in ("total", "positions", "by_status")}}
