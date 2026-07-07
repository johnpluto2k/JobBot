"""Interview prep scheduler: turn an interview date into a dated, backward-planned
prep schedule (calendar-ready), tuned to the firm's hiring process.

Produces plain event dicts that map directly onto Google Calendar events (the
`calendar_events()` helper), so the plan can be pushed to a connected calendar.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from .db import connect
from .questions import FIRM_NOTES

# Backward plan: offset-from-interview (days before) -> (title, focus)
PLAN_TEMPLATE: list[tuple[int, str, str]] = [
    (7, "Company + role research", "Build a 1-page brief: recent news, the team's work, why-this-firm angle."),
    (6, "Story bank review", "Rehearse 6–8 STAR+ stories aloud; tighten Results and add +Reflection."),
    (4, "Technical / case prep", "Drill the firm's gating content (3-statement, ITGC/SOX, SQL, or case frameworks)."),
    (3, "Behavioral drills", "Time 5 behavioral answers; score each with the rubric and fix the weakest."),
    (2, "Full mock interview", "Run a full mock round in character; record and review pacing + fillers."),
    (1, "Light review + logistics", "Skim notes, confirm time/link/dress, prep your questions, rest."),
]

FIRM_DEFAULT_ROUNDS = {
    "big4": "first round", "ib": "superday", "tech": "on-site loop",
    "fintech": "team loop", "corporate": "panel", "consulting": "case round",
}


def build_prep_plan(company: str, role: str, firm_type: str | None,
                    interview_date: str, start_hour: int = 18) -> dict:
    """interview_date: ISO 'YYYY-MM-DD' (optionally with 'THH:MM'). Returns a
    plan with dated blocks for the days we still have before the interview."""
    idt = _parse_dt(interview_date)
    today = date.today()
    days_until = (idt.date() - today).days

    blocks = []
    for offset, title, focus in PLAN_TEMPLATE:
        day = idt.date() - timedelta(days=offset)
        if day < today:
            continue  # skip days already passed
        blocks.append({
            "date": day.isoformat(),
            "title": f"Prep: {title} — {company}",
            "focus": focus,
            "start_hour": start_hour,
            "duration_min": 75,
        })
    note = FIRM_NOTES.get(firm_type or "", "")
    return {
        "company": company, "role": role, "firm_type": firm_type,
        "interview_date": idt.isoformat(), "days_until": days_until,
        "firm_note": note, "blocks": blocks,
    }


def calendar_events(plan: dict) -> list[dict]:
    """Google Calendar-compatible event dicts for each prep block + the interview."""
    events = []
    for b in plan["blocks"]:
        start = datetime.fromisoformat(f"{b['date']}T{b['start_hour']:02d}:00:00")
        end = start + timedelta(minutes=b["duration_min"])
        events.append({
            "summary": b["title"],
            "description": b["focus"] + (f"\n\nFirm: {plan['firm_note']}" if plan["firm_note"] else ""),
            "start": {"dateTime": start.isoformat()},
            "end": {"dateTime": end.isoformat()},
        })
    idt = datetime.fromisoformat(plan["interview_date"])
    events.append({
        "summary": f"INTERVIEW — {plan['role']} @ {plan['company']}",
        "description": f"{plan.get('firm_note','')}",
        "start": {"dateTime": idt.isoformat()},
        "end": {"dateTime": (idt + timedelta(hours=1)).isoformat()},
    })
    return events


def schedule_interview(company: str, role: str, firm_type: str | None,
                       interview_date: str, round_name: str | None = None) -> int:
    idt = _parse_dt(interview_date)
    rn = round_name or FIRM_DEFAULT_ROUNDS.get(firm_type or "", "interview")
    con = connect()
    cur = con.execute(
        "INSERT INTO interviews (company, role_title, round_name, firm_type, scheduled_at) "
        "VALUES (?,?,?,?,?)", (company, role, rn, firm_type, idt.isoformat()))
    con.commit()
    rid = cur.lastrowid
    con.close()
    return rid


def _parse_dt(s: str) -> datetime:
    s = s.strip()
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt if "T" in s or " " in s else dt.replace(hour=10)
        except ValueError:
            continue
    raise SystemExit(f"Could not parse interview date '{s}' (use YYYY-MM-DD or YYYY-MM-DDTHH:MM).")
