"""Shared, read-only evidence for the dashboard and command-line career coaches."""
from __future__ import annotations

import json
import re
from contextlib import closing
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr

from . import config
from .db import connect_readonly


def _utc(value: str | None) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value or "")
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _sync_freshness(now: datetime) -> dict:
    path = config.OUTPUT_DIR / "gmail_sync_status.json"
    try:
        status = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(status, dict):
            raise ValueError("Expected a JSON object")
    except (OSError, ValueError) as exc:
        return {"state": "unknown", "last_successful_sync": None,
                "last_error": None, "status_error": str(exc)}
    synced = _utc(status.get("last_sync"))
    age = (now - synced).total_seconds() if synced else None
    state = "fresh"
    if status.get("last_error"):
        state = "error"
    elif age is None or age < 0:
        state = "unknown"
    elif age > 3600:  # The normal sync cadence is fifteen minutes.
        state = "stale"
    return {
        "state": state,
        "last_successful_sync": status.get("last_sync"),
        "last_error": status.get("last_error"),
        "last_error_at": status.get("last_error_at"),
    }


def _is_acknowledgement(row: dict) -> bool:
    """A narrow display hint; never reclassify or mark stored mail handled."""
    address = parseaddr(row.get("sender") or "")[1].lower()
    automated = re.search(r"(?:^|[._-])(?:no[._-]?reply|do[._-]?not[._-]?reply)(?:[._-]|@)", address)
    subject = row.get("subject") or ""
    acknowledgement = re.search(
        r"thank(?:s| you) for (?:applying|your (?:application|interest))|"
        r"application (?:has been |was )?received|received your application|"
        r"application confirmation", subject, re.I,
    )
    action = re.search(r"interview|assessment|offer|schedule|action required|deadline", subject, re.I)
    return bool(row.get("category") == "recruiter_reply" and automated and acknowledgement and not action)


def build_snapshot(now: datetime | None = None) -> dict:
    """Read existing data only. Missing sections stay explicit instead of becoming zero."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    out: dict = {"generated_at": now.isoformat(), "warnings": []}
    out["freshness"] = _sync_freshness(now)
    state = out["freshness"]["state"]
    if state != "fresh":
        description = {
            "error": "Gmail sync has failed.",
            "stale": "Gmail data is out of date.",
            "unknown": "Gmail data freshness is unknown.",
        }[state]
        out["warnings"].append(
            f"{description} Check the last successful sync before drawing conclusions "
            "about recent applications or recruiter activity."
        )

    apps = None
    try:
        from .applications import build_applications, summary

        apps = build_applications(read_only=True)
        out["funnel"] = summary(apps)
    except Exception as exc:
        out["funnel_error"] = str(exc)

    try:
        with closing(connect_readonly()) as con:
            queries = {
                "upcoming_interviews": (
                    "SELECT id, company, role_title, round_name, scheduled_at, status "
                    "FROM interviews WHERE status IN ('scheduled','prepped') "
                    "AND datetime(scheduled_at)>=datetime(?) ORDER BY datetime(scheduled_at) LIMIT 10",
                    (now.isoformat(),),
                ),
                "interviews_needing_update": (
                    "SELECT id, company, role_title, round_name, scheduled_at, status "
                    "FROM interviews WHERE status IN ('scheduled','prepped') "
                    "AND (datetime(scheduled_at)<datetime(?) OR datetime(scheduled_at) IS NULL) "
                    "ORDER BY scheduled_at DESC LIMIT 10", (now.isoformat(),),
                ),
                "followups_due": (
                    "SELECT id, contact_name, company, kind, followup_date FROM outreach "
                    "WHERE status='drafted' AND date(followup_date)<=date(?) "
                    "ORDER BY followup_date LIMIT 10", (now.isoformat(),),
                ),
                "fresh_high_priority_jobs": (
                    "SELECT id, title, company, location, url, date_posted, created_at, priority "
                    "FROM jobs WHERE status='new' AND datetime(created_at)>=datetime(?) "
                    "AND datetime(COALESCE(NULLIF(date_posted,''),created_at))>=datetime(?) "
                    "ORDER BY priority DESC, id DESC LIMIT 5",
                    ((now - timedelta(days=14)).isoformat(),) * 2,
                ),
            }
            for name, (sql, params) in queries.items():
                try:
                    out[name] = [dict(row) for row in con.execute(sql, params)]
                except Exception as exc:
                    out[name + "_error"] = str(exc)

            try:
                out["freshness"]["latest_email"] = con.execute(
                    "SELECT MAX(received_at) FROM tracked_emails"
                ).fetchone()[0]
                out["freshness"]["latest_job"] = con.execute(
                    "SELECT MAX(created_at) FROM jobs"
                ).fetchone()[0]
                out["freshness"]["latest_watch"] = con.execute(
                    "SELECT MAX(last_watch_at) FROM companies"
                ).fetchone()[0]
            except Exception as exc:
                out["freshness_error"] = str(exc)

            try:
                groups: dict[str, list] = {
                    "unhandled_recruiter_email": [], "older_unhandled_email": [],
                    "automated_acknowledgements": [],
                }
                counts = {key: 0 for key in groups}
                cutoff = now.date() - timedelta(days=30)
                for row in con.execute(
                    "SELECT id, received_at, company, category, sender, subject FROM tracked_emails "
                    "WHERE handled=0 AND category IN "
                    "('interview_invite','assessment','offer','recruiter_reply') "
                    "ORDER BY received_at DESC, id DESC"
                ):
                    item = dict(row)
                    received = _utc(item["received_at"])
                    if _is_acknowledgement(item):
                        key = "automated_acknowledgements"
                    elif received is None or received.date() < cutoff:
                        key = "older_unhandled_email"
                    else:
                        key = "unhandled_recruiter_email"
                    counts[key] += 1
                    if len(groups[key]) < 10:
                        groups[key].append(item)
                out.update(groups)
                out["email_counts"] = counts
            except Exception as exc:
                out["email_error"] = str(exc)
    except Exception as exc:
        out["db_error"] = str(exc)

    try:
        if apps is None:
            raise ValueError("Application history unavailable; growth plan was not inferred from missing data")
        from .growth import build_plan

        plan = build_plan(applications=apps)
        out["growth_insights"] = plan.get("insights", [])
        out["growth_focus_fields"] = [f["field"] for f in plan.get("per_field", [])]
    except (Exception, SystemExit) as exc:
        out["growth_error"] = str(exc)
    if any(key.endswith("_error") for key in out):
        out["warnings"].append("Some snapshot sections are unavailable. Missing data is not evidence of no activity.")
    return out
