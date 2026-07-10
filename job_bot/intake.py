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
        # Get or create company
        from . import companies

        company, created = companies.get_or_create(company_disp)
        company_id = company["id"]

        # Create job entry
        today = date.today().isoformat()
        cur = con.execute("""
            INSERT INTO jobs
            (title, company, url, site, status, date_posted, created_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            title.strip(),
            company_disp,
            url.strip(),
            portal_lower,
            status_lower,
            today,
        ))
        con.commit()
        job_id = cur.lastrowid

        return {
            "id": job_id,
            "company_id": company_id,
            "company_name": company_disp,
            "job_title": title.strip(),
            "url": url.strip(),
            "status": status_lower,
            "portal": portal_lower,
            "logged_at": today,
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
