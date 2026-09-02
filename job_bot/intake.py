"""Manual job intake — log a job John found and applied to.

This is the primary workflow in the company-first tracker model: John finds
jobs on LinkedIn, Indeed, Jobright, etc., applies manually, then logs them
here with a company, title, and portal. The bot links it to the companies
table and tracks the application.

Use via:
  - CLI: python -m job_bot.intake <url> <company> <title> [--portal <portal>] [--status <status>]
  - API: POST /api/intake
  - Python: from job_bot.intake import log_job; log_job(...)
"""

from __future__ import annotations

import argparse
from datetime import date
from typing import Optional

from . import applications
from .db import connect


# Valid portals (job boards where John searches)
VALID_PORTALS = {
    "indeed", "linkedin", "jobright", "glassdoor", "ziprecruiter",
    "workday", "greenhouse", "handshake", "smith", "email", "other"
}

# Valid statuses
VALID_STATUSES = {"applied", "saved", "rejected", "offer"}


def log_job(
    url: str,
    company_name: str,
    title: str,
    portal: str = "other",
    status: str = "applied",
    notes: str | None = None,
) -> dict:
    """Log a job John found and applied to manually.

    Args:
        url: The job posting URL
        company_name: Company name (will be normalized)
        title: Job title
        portal: Where John found it (indeed, linkedin, jobright, etc.)
        status: Application status (applied, saved, rejected, offer)
        notes: Optional notes about the application

    Returns:
        dict with keys: id, company_id, company_name, job_title, url, status, portal, logged_at

    Raises:
        ValueError: if inputs are invalid
    """
    # Validate inputs
    if not url or not url.strip():
        raise ValueError("URL is required")
    if not company_name or not company_name.strip():
        raise ValueError("Company name is required")
    if not title or not title.strip():
        raise ValueError("Job title is required")

    portal_lower = portal.lower() if portal else "other"
    if portal_lower not in VALID_PORTALS:
        raise ValueError(f"Invalid portal: {portal}. Must be one of: {', '.join(sorted(VALID_PORTALS))}")

    status_lower = status.lower() if status else "applied"
    if status_lower not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}. Must be one of: {', '.join(sorted(VALID_STATUSES))}")

    # Normalize company name
    company_disp = applications.canon(company_name)
    if not company_disp or company_disp.lower() in applications._EXCLUDE:
        raise ValueError(f"Invalid or excluded company: {company_name}")

    con = connect()
    try:
        # Re-logging a URL is a normal daily action - correcting a status, fixing a
        # typo. jobs.url is UNIQUE and this used to be a bare INSERT, so the second
        # call raised IntegrityError and surfaced as an opaque 500. Look first and
        # treat a repeat as an update.
        existing = con.execute("SELECT id FROM jobs WHERE url = ?", (url.strip(),)).fetchone()

        # Get or create company. Record the portal on the company too - that is what
        # the companies.portals column is for, and it keeps the provenance that used
        # to live in jobs.site (see below).
        from . import companies

        company, created = companies.get_or_create(company_disp, portals=[portal_lower])
        company_id = company["id"]
        # Use the tracker row's name, not our own canon() of the raw input. When
        # "KPMG USA" and "kpmg" resolve to the same company, both jobs must be
        # filed under the one name that company row already carries - otherwise
        # the jobs table grows two spellings for a single employer even though
        # the tracker correctly holds one row.
        company_disp = company.get("name") or company_disp

        # site='tracker', NOT the portal name.
        #
        # applications.build_applications() - the canonical funnel, and the number
        # CLAUDE.md tells the coach to trust - only reads
        #   WHERE site IN ('email','tracker','ledger')
        # while this wrote site='linkedin'/'indeed'/etc. So every job logged through
        # the documented manual-intake flow was invisible to the funnel: four
        # status='applied' rows existed and none of them counted. The portal is kept
        # on the company row above and in the job's notes.
        today = date.today().isoformat()
        portal_note = f"[{portal_lower}]"
        note_text = f"{portal_note} {notes}".strip() if notes else portal_note

        try:
            if existing:
                con.execute("""
                    UPDATE jobs
                       SET company_id=?, title=?, company=?, site='tracker',
                           status=?, date_posted=?, notes=?
                     WHERE id=?
                """, (company_id, title.strip(), company_disp, status_lower, today,
                      note_text, existing["id"]))
                job_id = existing["id"]
            else:
                cur = con.execute("""
                    INSERT INTO jobs
                    (company_id, title, company, url, site, status, date_posted, notes, created_at)
                    VALUES (?, ?, ?, ?, 'tracker', ?, ?, ?, datetime('now'))
                """, (
                    company_id,
                    title.strip(),
                    company_disp,
                    url.strip(),
                    status_lower,
                    today,
                    note_text,
                ))
                job_id = cur.lastrowid
            con.commit()
        except Exception:
            # get_or_create commits on its own connection, so a failure here used to
            # leave a company row behind for a job that was never logged.
            con.rollback()
            if created:
                con.execute("DELETE FROM companies WHERE id=?", (company_id,))
                con.commit()
            raise

        return {
            "id": job_id,
            "company_id": company_id,
            "company_name": company_disp,
            "job_title": title.strip(),
            "url": url.strip(),
            "status": status_lower,
            "portal": portal_lower,
            "logged_at": today,
            "updated": bool(existing),
        }

    finally:
        con.close()


def main():
    """CLI entry point: python -m job_bot.intake"""
    parser = argparse.ArgumentParser(
        description="Log a job you found and applied to"
    )
    parser.add_argument("url", help="Job posting URL")
    parser.add_argument("company", help="Company name")
    parser.add_argument("title", help="Job title")
    parser.add_argument(
        "--portal",
        default="other",
        help=f"Job board (default: other). Options: {', '.join(sorted(VALID_PORTALS))}",
    )
    parser.add_argument(
        "--status",
        default="applied",
        help=f"Application status (default: applied). Options: {', '.join(sorted(VALID_STATUSES))}",
    )
    parser.add_argument("--notes", help="Optional notes")

    args = parser.parse_args()

    try:
        result = log_job(
            url=args.url,
            company_name=args.company,
            title=args.title,
            portal=args.portal,
            status=args.status,
            notes=args.notes,
        )
        print(f"Logged: {result['company_name']} - {result['job_title']}")
        print(f"  URL: {result['url']}")
        print(f"  Portal: {result['portal']}")
        print(f"  Status: {result['status']}")
    except ValueError as e:
        print(f"Error: {e}", file=__import__("sys").stderr)
        exit(1)


if __name__ == "__main__":
    main()
