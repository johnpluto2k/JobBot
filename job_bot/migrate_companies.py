"""Migration script: populate the companies table from existing job data.

This script:
1. Extracts all distinct companies from the jobs table
2. Normalizes names using applications.canon()
3. Dedupes by name_normalized
4. For each company, creates a row with:
   - career_site_url parsed from jobs.url
   - ats_platform parsed from jobs.site or URL
   - portals from jobs.site
   - target_fields from classified job titles
   - tier from master_profile.json
   - created_at from earliest job.date_posted

Idempotent: INSERT OR IGNORE on unique name_normalized.

Run with: python -m job_bot.migrate_companies [--dry-run] [--backup]
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import applications, config
from .db import DB_PATH, connect


def parse_ats_platform(url: str, site: str) -> Optional[str]:
    """Infer ATS platform from URL or site."""
    url_lower = (url or "").lower()
    site_lower = (site or "").lower()

    # URL-based detection
    if "workday" in url_lower:
        return "Workday"
    if "greenhouse" in url_lower or "gh.app" in url_lower:
        return "Greenhouse"
    if "icims" in url_lower or "ats.icims" in url_lower:
        return "iCIMS"
    if "taleo" in url_lower:
        return "Taleo"
    if "bamboohr" in url_lower or "bamboo" in url_lower:
        return "BambooHR"
    if "adp" in url_lower:
        return "ADP"
    if "successfactors" in url_lower:
        return "SuccessFactors"
    if "equest" in url_lower or "kforce.com" in url_lower:
        return "eQuest"

    # Site-based detection
    if site_lower == "workday":
        return "Workday"
    if site_lower == "greenhouse":
        return "Greenhouse"

    return None


def parse_portals(site: str) -> list[str]:
    """Map job site to portal name(s)."""
    if not site:
        return []

    site_lower = site.lower()

    mapping = {
        "indeed": ["Indeed"],
        "linkedin": ["LinkedIn"],
        "jobright": ["Jobright"],
        "glassdoor": ["Glassdoor"],
        "ziprecruiter": ["ZipRecruiter"],
        "workday": ["Workday"],
        "greenhouse": ["Company Career Site"],
        "email": [],  # Don't count email/tracker as a portal
        "tracker": [],
        "ledger": [],
    }

    return mapping.get(site_lower, [])


def extract_tier(company_name: str, master_profile: dict) -> Optional[str]:
    """Infer company tier from master_profile.json."""
    if not master_profile or "target_companies" not in master_profile:
        return None

    company_norm = applications.canon(company_name)
    if not company_norm:
        return None

    targets = master_profile.get("target_companies", {})

    # Check if company is listed in each tier
    big4 = [applications.canon(n) for n in targets.get("big4", [])]
    mid = [applications.canon(n) for n in targets.get("mid_tier", [])]
    boutique = [applications.canon(n) for n in targets.get("boutique", [])]

    if company_norm in big4:
        return "Big4"
    if company_norm in mid:
        return "mid-tier"
    if company_norm in boutique:
        return "boutique"

    return None


def run_migration(dry_run: bool = False, backup: bool = True) -> dict:
    """Execute the migration.

    Seed the companies table from applications.build_applications() — the canonical
    source of truth. This ensures we only track companies where John actually applied.

    Returns: {
        total_companies: int,
        created: int,
        skipped: int,
        errors: list[str]
    }
    """
    if backup:
        backup_path = DB_PATH.parent / f"{DB_PATH.name}.backup_before_companies"
        print(f"Backing up database to {backup_path}")
        shutil.copy2(DB_PATH, backup_path)

    con = connect()

    # Load master profile for tier hints
    profile_path = config.OUTPUT_DIR / "master_profile.json"
    master_profile = {}
    if profile_path.exists():
        try:
            with open(profile_path) as f:
                master_profile = json.load(f)
        except Exception as e:
            print(f"Warning: Could not load master profile: {e}")

    try:
        # Use applications.build_applications() as the canonical source
        # This already applies deduping, normalization, and the any_applied_signal filter
        canonical_apps = applications.build_applications()
        print(f"\nMigrating {len(canonical_apps)} applications (canonical source)...")

        # For each application company, gather data from jobs
        created = 0
        skipped = 0
        errors = []

        for app in canonical_apps:
            company_disp = app["company"]
            company_roles = app["roles"]

            # Find all job entries for this company (to gather career_site_url, portals, etc)
            job_rows = con.execute("""
                SELECT DISTINCT site, url, date_posted
                FROM jobs
                WHERE company IN (
                    SELECT DISTINCT company FROM jobs WHERE LOWER(company) LIKE ?
                )
                ORDER BY date_posted DESC
            """, (f"%{company_disp.split()[0]}%",)).fetchall()

            # Merge data from job entries
            portals_set = set()
            ats_platforms_set = set()

            for job_row in job_rows:
                job_dict = dict(job_row)
                if job_dict.get("site"):
                    portals_set.update(parse_portals(job_dict["site"]))
                if job_dict.get("url"):
                    ats = parse_ats_platform(job_dict["url"], job_dict.get("site"))
                    if ats:
                        ats_platforms_set.add(ats)

            # Target fields from the application's classified roles
            target_fields = list(set(
                applications.classify_field(r) for r in company_roles if r
            ))
            target_fields = [f for f in target_fields if f != "Other"]

            # Tier
            tier = extract_tier(company_disp, master_profile) or "other"

            try:
                if dry_run:
                    print(f"  [DRY RUN] Would create: {company_disp}")
                else:
                    con.execute("""
                        INSERT OR IGNORE INTO companies
                        (name, name_normalized, ats_platform, portals, target_fields, tier, created_at, last_checked, next_check_due)
                        VALUES (?, ?, ?, ?, ?, ?, datetime('now'), date('now'), date('now', '+7 days'))
                    """, (
                        company_disp,
                        applications.canon(company_disp),
                        list(ats_platforms_set)[0] if ats_platforms_set else None,
                        json.dumps(sorted(portals_set)),
                        json.dumps(target_fields),
                        tier,
                    ))
                    con.commit()
                    created += 1

            except Exception as e:
                errors.append(f"Error creating {company_disp}: {e}")

        if not dry_run:
            # Verify the count
            final_count = con.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
            print(f"\nMigration complete: {final_count} companies in table")

        return {
            "total_companies": len(canonical_apps),
            "created": created,
            "skipped": skipped,
            "errors": errors,
        }

    finally:
        con.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate companies from jobs table")
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen without doing it")
    parser.add_argument("--no-backup", action="store_true", help="Skip database backup")
    args = parser.parse_args()

    print("Starting companies migration...")
    result = run_migration(
        dry_run=args.dry_run,
        backup=not args.no_backup
    )

    print(f"\nResults:")
    print(f"  Total companies to create: {result['total_companies']}")
    print(f"  Created: {result['created']}")
    print(f"  Skipped: {result['skipped']}")
    if result["errors"]:
        print(f"  Errors:")
        for err in result["errors"]:
            print(f"    - {err}")


if __name__ == "__main__":
    main()
