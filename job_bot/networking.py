"""Phase 6: networking intelligence — find warm contacts at a company, draft
outreach, and schedule a follow-up cadence (logged to the outreach table)."""

from __future__ import annotations

from datetime import date, timedelta

from .connections import connection_strength, matches_for_company
from .db import connect
from .decision_models import ConnectionMatch
from .outreach import draft

# follow-up cadence in days after the first message
CADENCE_DAYS = [0, 4, 9]


def find_contacts(company: str) -> tuple[list[ConnectionMatch], float, bool]:
    con = connect()
    matches = matches_for_company(con, company)
    con.close()
    strength, recruiter = connection_strength(matches)
    return matches, strength, recruiter


def _kind_for(contact: ConnectionMatch) -> str:
    if contact.relationship == "recruiter":
        return "referral_request"
    if contact.warmth >= 0.5:
        return "referral_request"
    return "intro"


def build_plan(company: str, role_title: str, candidate: str = "John",
               max_contacts: int = 3, use_llm: bool | None = None,
               log: bool = True) -> dict:
    matches, strength, recruiter = find_contacts(company)
    today = date.today()
    plan_contacts = []
    con = connect() if log else None
    for c in matches[:max_contacts]:
        kind = _kind_for(c)
        message = draft(kind, c, company, role_title, candidate, use_llm=use_llm)
        followups = [(today + timedelta(days=d)).isoformat() for d in CADENCE_DAYS]
        entry = {
            "contact": c.name, "title": c.title, "relationship": c.relationship,
            "warmth": c.warmth, "kind": kind, "message": message,
            "send_on": followups[0], "followup_dates": followups[1:],
        }
        plan_contacts.append(entry)
        if con is not None:
            con.execute(
                "INSERT INTO outreach (contact_name, company, role_title, kind, channel, "
                "message, status, sent_date, followup_date) VALUES (?,?,?,?,?,?,?,?,?)",
                (c.name, company, role_title, kind, "linkedin", message, "drafted",
                 followups[0], followups[1] if len(followups) > 1 else None),
            )
    if con is not None:
        con.commit()
        con.close()

    return {
        "company": company,
        "role_title": role_title,
        "connection_strength": strength,
        "recruiter_available": recruiter,
        "contacts": plan_contacts,
        "cadence_days": CADENCE_DAYS,
    }
