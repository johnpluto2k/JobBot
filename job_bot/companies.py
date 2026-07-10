"""Company tracker — CRUD operations and querying for the companies table.

This module manages the canonical list of target companies John is monitoring,
including their career sites, ATS platforms, and check-in schedule.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Optional

from .db import connect


def get_or_create(name: str, **kwargs) -> tuple[dict, bool]:
    """Get a company by name_normalized, or create it if it doesn't exist.

    Returns: (company_dict, created: bool)

    Kwargs can include: career_site_url, ats_platform, portals, target_fields, tier, notes.
    """
    from . import applications  # Avoid circular import

    name_norm = applications.canon(name)
    if not name_norm:
        raise ValueError(f"Cannot normalize company name: {name}")

    con = connect()
    try:
        # Try to fetch existing
        row = con.execute(
            "SELECT * FROM companies WHERE name_normalized = ?",
            (name_norm,)
        ).fetchone()

        if row:
            return dict(row), False

        # Create new with proper error handling for concurrent inserts
        portals_json = json.dumps(kwargs.get("portals", []))
        fields_json = json.dumps(kwargs.get("target_fields", []))

        today = date.today().isoformat()
        next_due = (date.today() + timedelta(days=7)).isoformat()

        try:
            cur = con.execute("""
                INSERT INTO companies
                (name, name_normalized, career_site_url, ats_platform, portals, target_fields, tier, notes, last_checked, next_check_due)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name,
                name_norm,
                kwargs.get("career_site_url"),
                kwargs.get("ats_platform"),
                portals_json,
                fields_json,
                kwargs.get("tier", "other"),
                kwargs.get("notes"),
                today,
                next_due,
            ))
            con.commit()

            # Fetch the new row
            new_row = con.execute(
                "SELECT * FROM companies WHERE id = ?",
                (cur.lastrowid,)
            ).fetchone()
            return dict(new_row), True
        except Exception as e:
            con.rollback()
            if "UNIQUE constraint failed" in str(e):
                # Another thread created it first, fetch it
                row = con.execute(
                    "SELECT * FROM companies WHERE name_normalized = ?",
                    (name_norm,)
                ).fetchone()
                if row:
                    return dict(row), False
            raise
    finally:
        con.close()


def get_by_id(company_id: int) -> dict | None:
    """Fetch a company by ID."""
    con = connect()
    try:
        row = con.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def get_by_name_normalized(name_normalized: str) -> dict | None:
    """Fetch a company by name_normalized (canonical form)."""
    con = connect()
    try:
        row = con.execute("SELECT * FROM companies WHERE name_normalized = ?", (name_normalized,)).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def list_all() -> list[dict]:
    """Return all companies, sorted by next_check_due (soonest first), then name."""
    con = connect()
    try:
        rows = con.execute("""
            SELECT * FROM companies
            ORDER BY next_check_due ASC, name ASC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def due_for_check() -> list[dict]:
    """Return companies where next_check_due <= today, sorted by due date."""
    con = connect()
    try:
        today = date.today().isoformat()
        rows = con.execute("""
            SELECT * FROM companies
            WHERE next_check_due <= ?
            ORDER BY next_check_due ASC
        """, (today,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def mark_checked(company_id: int, next_check_in_days: int = 7) -> dict:
    """Mark a company as checked today, and schedule next check for today+N days.

    Returns: updated company dict

    Raises: ValueError if company does not exist
    """
    con = connect()
    try:
        today = date.today().isoformat()
        next_due = (date.today() + timedelta(days=next_check_in_days)).isoformat()

        con.execute("""
            UPDATE companies
            SET last_checked = ?, next_check_due = ?
            WHERE id = ?
        """, (today, next_due, company_id))
        con.commit()

        result = get_by_id(company_id)
        if result is None:
            raise ValueError(f"Company {company_id} not found")
        return result
    finally:
        con.close()


def update(company_id: int, **kwargs) -> dict:
    """Update company fields.

    Kwargs: name, career_site_url, ats_platform, portals, target_fields, tier, notes

    Returns: updated company dict

    Raises: ValueError if company does not exist
    """
    con = connect()
    try:
        # Check company exists first
        existing = get_by_id(company_id)
        if existing is None:
            raise ValueError(f"Company {company_id} not found")

        # Build the UPDATE statement dynamically
        allowed_fields = {
            "name", "career_site_url", "ats_platform", "portals",
            "target_fields", "tier", "notes"
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return existing

        # Convert list fields to JSON
        if "portals" in updates and isinstance(updates["portals"], list):
            updates["portals"] = json.dumps(updates["portals"])
        if "target_fields" in updates and isinstance(updates["target_fields"], list):
            updates["target_fields"] = json.dumps(updates["target_fields"])

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [company_id]

        con.execute(f"UPDATE companies SET {set_clause} WHERE id = ?", values)
        con.commit()

        return get_by_id(company_id)
    finally:
        con.close()


def insert(name: str, **kwargs) -> int:
    """Insert a new company (does not check for duplicates).

    Returns: company id

    Use get_or_create() if you want to avoid duplicates.
    """
    from . import applications

    name_norm = applications.canon(name)
    if not name_norm:
        raise ValueError(f"Cannot normalize company name: {name}")

    con = connect()
    try:
        portals_json = json.dumps(kwargs.get("portals", []))
        fields_json = json.dumps(kwargs.get("target_fields", []))

        today = date.today().isoformat()
        next_due = (date.today() + timedelta(days=7)).isoformat()

        cur = con.execute("""
            INSERT INTO companies
            (name, name_normalized, career_site_url, ats_platform, portals, target_fields, tier, notes, last_checked, next_check_due)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            name_norm,
            kwargs.get("career_site_url"),
            kwargs.get("ats_platform"),
            portals_json,
            fields_json,
            kwargs.get("tier", "other"),
            kwargs.get("notes"),
            today,
            next_due,
        ))
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def _deserialize(row: dict) -> dict:
    """Convert JSON-encoded fields back to Python objects."""
    if not row:
        return row

    result = dict(row)
    if result.get("portals"):
        try:
            result["portals"] = json.loads(result["portals"])
        except (json.JSONDecodeError, TypeError):
            result["portals"] = []

    if result.get("target_fields"):
        try:
            result["target_fields"] = json.loads(result["target_fields"])
        except (json.JSONDecodeError, TypeError):
            result["target_fields"] = []

    return result
