"""SQLite store for connections and application/decision tracking.

This is the system's persistent control center — Phase 3 writes connections and
decision logs here, and later phases (application tracking dashboard) build on
the same database.
"""

from __future__ import annotations

import sqlite3

from . import config

DB_PATH = config.OUTPUT_DIR / "job_bot.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS connections (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT,
    company       TEXT,
    company_norm  TEXT,
    title         TEXT,
    relationship  TEXT,        -- recruiter | first_degree | second_degree | umd | pse | iefs | terptax | alum
    warmth        REAL,
    location      TEXT,
    notes         TEXT,
    source        TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_conn_company ON connections(company_norm);

CREATE TABLE IF NOT EXISTS decisions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    company       TEXT,
    title         TEXT,
    verdict       TEXT,
    ats_score     REAL,
    competition   REAL,
    connection    REAL,
    report_json   TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS outreach (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_name  TEXT,
    company       TEXT,
    role_title    TEXT,
    kind          TEXT,        -- referral_request | intro | follow_up | thank_you
    channel       TEXT,        -- linkedin | email
    message       TEXT,
    status        TEXT DEFAULT 'drafted',  -- drafted | sent | replied | no_reply
    sent_date     TEXT,
    followup_date TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rejections (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    company       TEXT,
    role_title    TEXT,
    role_type     TEXT,
    stage         TEXT,        -- ats_screen | assessment | recruiter_screen | first_round | superday | final | unknown
    ats_score     REAL,
    market_tier   TEXT,
    platform      TEXT,
    source        TEXT,        -- manual | inbox
    rejected_on   TEXT,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS interviews (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    company       TEXT,
    role_title    TEXT,
    round_name    TEXT,        -- recruiter screen | first round | superday | technical | final
    firm_type     TEXT,
    scheduled_at  TEXT,        -- ISO datetime of the interview
    status        TEXT DEFAULT 'scheduled',  -- scheduled | prepped | done | passed | rejected
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tracked_emails (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at   TEXT,
    sender        TEXT,
    subject       TEXT,
    company       TEXT,
    category      TEXT,        -- interview_invite | recruiter_reply | rejection | assessment | offer | other
    action        TEXT,
    gmail_id      TEXT,        -- Gmail thread/message id, for dedupe on re-scan
    handled       INTEGER DEFAULT 0,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS notifications (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    kind          TEXT,         -- fresh_job | deadline | followup
    ref           TEXT,         -- job url / offer id / etc (dedupe key)
    company       TEXT,
    title         TEXT,
    channel       TEXT,         -- console | webhook
    payload       TEXT,
    sent_at       TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_notif_ref ON notifications(ref);

CREATE TABLE IF NOT EXISTS cover_variants (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    company       TEXT,
    role_title    TEXT,
    firm_type     TEXT,         -- big4 | bank | tech | other
    style         TEXT,         -- formal | conversational
    angle         TEXT,         -- finance | tech
    label         TEXT,         -- A | B
    sent          INTEGER DEFAULT 0,
    sent_date     TEXT,
    response      TEXT DEFAULT 'pending',  -- pending | none | reply | interview
    response_date TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS offers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    company       TEXT,
    role_title    TEXT,
    location      TEXT,
    base          REAL,         -- annual base salary (USD)
    bonus         REAL,         -- expected annual bonus / signing amortized (USD)
    equity        REAL,         -- annual equity value (USD)
    benefits_value REAL,        -- estimated annual benefits value (USD)
    col_index     REAL,         -- cost-of-living index (100 = US average)
    growth        REAL,         -- 1-5 subjective company growth / trajectory
    fit           REAL,         -- 1-5 subjective role/team fit
    deadline      TEXT,         -- decision deadline (ISO date)
    status        TEXT DEFAULT 'open',   -- open | accepted | declined | expired
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scrape_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    term          TEXT,
    location      TEXT,
    sites         TEXT,         -- comma-joined site list
    results       INTEGER,      -- postings returned
    scraped_at    TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_scrape_term ON scrape_log(term, location);

CREATE TABLE IF NOT EXISTS jobs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id    INTEGER,       -- FK to companies table
    title         TEXT,
    company       TEXT,
    location      TEXT,
    site          TEXT,
    url           TEXT UNIQUE,
    date_posted   TEXT,
    market_tier   TEXT,
    tier_num      INTEGER,
    ats_score     REAL,
    priority      REAL,
    status        TEXT DEFAULT 'new',   -- new | applied | networking | interview | rejected | offer
    description   TEXT,
    notes         TEXT,          -- user notes about the application
    legit_score   REAL,          -- 0-100 posting legitimacy (higher = safer)
    legit_grade   TEXT,          -- ✅ Likely legit | ⚠️ Verify first | 🚩 High risk
    legit_flags   TEXT,          -- human-readable scam/ghost signals found
    recommendation TEXT,         -- ✅ Apply | 🟡 Maybe | 🚩 Verify | ⏭️ Skip (apply gate)
    seniority     TEXT,          -- intern | entry | mid | senior | lead | exec
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS companies (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL,
    name_normalized   TEXT NOT NULL UNIQUE,
    career_site_url   TEXT,
    ats_platform      TEXT,        -- JSON list or single platform: ["Workday", "Greenhouse"] or "Workday"
    portals           TEXT,        -- JSON list: ["Indeed", "LinkedIn", "Jobright", ...]
    target_fields     TEXT,        -- JSON list: ["IT Audit", "Audit & Assurance", ...]
    tier              TEXT,        -- Big4 | mid-tier | boutique | other
    notes             TEXT,
    last_checked      TEXT,        -- ISO date YYYY-MM-DD
    next_check_due    TEXT,        -- ISO date YYYY-MM-DD
    created_at        TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_company_norm ON companies(name_normalized);
CREATE INDEX IF NOT EXISTS idx_company_due ON companies(next_check_due);

CREATE TABLE IF NOT EXISTS generated_resumes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT DEFAULT (datetime('now')),
    company       TEXT NOT NULL,
    role          TEXT NOT NULL,
    track         TEXT,
    ats_before    REAL,
    ats_after     REAL,
    folder_path   TEXT NOT NULL,
    jd_excerpt    TEXT
);
CREATE INDEX IF NOT EXISTS idx_generated_resumes_created ON generated_resumes(created_at);
"""


def _migrate(con: sqlite3.Connection) -> None:
    """Add columns introduced after a table already existed (idempotent)."""
    cols = {r["name"] for r in con.execute("PRAGMA table_info(tracked_emails)")}
    if "gmail_id" not in cols:
        con.execute("ALTER TABLE tracked_emails ADD COLUMN gmail_id TEXT")
    con.execute("CREATE INDEX IF NOT EXISTS idx_email_gmail ON tracked_emails(gmail_id)")

    # Add missing columns to jobs table
    job_cols = {r["name"] for r in con.execute("PRAGMA table_info(jobs)")}
    if "company_id" not in job_cols:
        con.execute("ALTER TABLE jobs ADD COLUMN company_id INTEGER")
    if "notes" not in job_cols:
        con.execute("ALTER TABLE jobs ADD COLUMN notes TEXT")
    con.commit()

    # Legitimacy + apply-gate columns on jobs (career-ops Block G integration).
    jcols = {r["name"] for r in con.execute("PRAGMA table_info(jobs)")}
    for col, decl in (("legit_score", "REAL"), ("legit_grade", "TEXT"),
                      ("legit_flags", "TEXT"), ("recommendation", "TEXT"),
                      ("seniority", "TEXT")):
        if col not in jcols:
            con.execute(f"ALTER TABLE jobs ADD COLUMN {col} {decl}")

    # Companies table (created via SCHEMA, but migrations for new columns go here).
    ccols = {r["name"] for r in con.execute("PRAGMA table_info(companies)")}
    # (No additional columns to migrate yet; the table is created fresh in SCHEMA.)

    con.commit()


def connect() -> sqlite3.Connection:
    config.ensure_dirs()
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    _migrate(con)
    return con
