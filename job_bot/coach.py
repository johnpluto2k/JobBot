"""Career-coach chat, grounded in COACH.md + a live pipeline snapshot.

This is the engine behind the dashboard's **Coach** tab (POST /api/coach). It
grounds Claude in two things, every turn:

1. ``COACH.md`` — the persona, tone (**balanced**), and the rules about which
   data sources are the source of truth.
2. A *live, read-only* snapshot of John's pipeline — the same funnel /
   interviews / follow-ups / recruiter-email / fresh-postings / growth facts the
   CLI ``coach_snapshot.py`` prints — so the coach answers from real numbers and
   never fabricates a company, count, or interview.

Judgment-heavy call → routed to ``config.ANTHROPIC_MODEL`` (the full model), the
same way ``cover_letter`` routes its judgment call. The snapshot is rebuilt on
every turn: this is John's single-user local app, the queries are cheap, and it
keeps the coaching current instead of stale from when the chat opened.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import config
from .db import connect

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COACH_MD = PROJECT_ROOT / "COACH.md"


def build_snapshot() -> dict:
    """Read-only live snapshot of the pipeline (mirrors ``coach_snapshot.py``).

    Every query here is a read — this never writes to the DB or any file. Each
    section is best-effort: a failure in one (e.g. a missing growth dependency)
    is captured as an ``*_error`` key instead of sinking the whole snapshot, so
    the coach still gets the funnel and time-sensitive items.
    """
    out: dict = {}

    # 1. Canonical funnel — the one source of truth (deduped, name-normalized).
    try:
        from .applications import summary

        out["funnel"] = summary()
    except Exception as exc:  # pragma: no cover - defensive, mirrors CLI
        out["funnel_error"] = str(exc)

    # 2. Time-sensitive items — straight SQL, no extra dependencies.
    try:
        con = connect()
        try:
            out["upcoming_interviews"] = [
                dict(r)
                for r in con.execute(
                    "SELECT company, role_title, round_name, scheduled_at, status "
                    "FROM interviews WHERE status IN ('scheduled','prepped') "
                    "ORDER BY scheduled_at LIMIT 10"
                )
            ]
            out["followups_due"] = [
                dict(r)
                for r in con.execute(
                    "SELECT contact_name, company, kind, followup_date FROM outreach "
                    "WHERE status='drafted' AND followup_date<=date('now') "
                    "ORDER BY followup_date LIMIT 10"
                )
            ]
            out["unhandled_recruiter_email"] = [
                dict(r)
                for r in con.execute(
                    "SELECT received_at, company, category FROM tracked_emails "
                    "WHERE handled=0 AND category IN "
                    "('interview_invite','assessment','offer','recruiter_reply') "
                    "ORDER BY received_at DESC LIMIT 10"
                )
            ]
            out["fresh_high_priority_jobs"] = [
                dict(r)
                for r in con.execute(
                    # "fresh" has to mean fresh. Unbounded, this ranked postings
                    # from July as today's opportunities - and COACH.md's whole
                    # premise is that the coaching is only worth anything because
                    # the numbers behind it are true.
                    "SELECT title, company, priority FROM jobs WHERE status='new' "
                    "AND created_at > datetime('now','-14 days') "
                    "ORDER BY priority DESC LIMIT 5"
                )
            ]
        finally:
            con.close()
    except Exception as exc:  # pragma: no cover - defensive
        out["db_error"] = str(exc)

    # 3. Growth plan — needs the pydantic-backed models; best-effort only.
    try:
        from .growth import build_plan

        plan = build_plan()
        out["growth_insights"] = plan.get("insights", [])
        out["growth_focus_fields"] = [f["field"] for f in plan.get("per_field", [])]
    except Exception as exc:  # pragma: no cover - optional dependency
        out["growth_error"] = str(exc)

    return out


def coach_system(snapshot: dict | None = None) -> str:
    """Build the coach's system prompt: persona (COACH.md) + live snapshot."""
    persona = COACH_MD.read_text(encoding="utf-8") if COACH_MD.exists() else ""
    snap = snapshot if snapshot is not None else build_snapshot()
    return (
        "You are John Bae's personal career coach, speaking with him live inside "
        "his job-search dashboard. The COACH.md block below defines your tone "
        "(balanced: specific praise for real wins, candid about stalling or "
        "avoidance) and which data you may trust. The LIVE SNAPSHOT is the "
        "current, real state of his pipeline.\n\n"
        "How to answer: coach, don't report. Answer what John actually asked "
        "using the one or two facts that matter — not a dump of every number. "
        "Lead with anything time-sensitive (an interview coming up, an overdue "
        "follow-up, unhandled recruiter email), give one honest observation "
        "grounded in the snapshot, and close with exactly one concrete next "
        "action. Never invent a number, company, interview, or 'you're doing "
        "great' the snapshot doesn't support — the coaching is only worth "
        "anything because it's trustworthy. Keep replies short and direct, like "
        "a text from a coach who respects his time (a few sentences, not a "
        "report). Use plain text, not markdown headers.\n\n"
        "=== COACH.md ===\n"
        f"{persona}\n\n"
        "=== LIVE SNAPSHOT (read-only, current pipeline state) ===\n"
        f"{json.dumps(snap, indent=2, default=str)}"
    )


def chat(messages: list[dict], snapshot: dict | None = None) -> str:
    """Run one coaching turn. ``messages`` is the full conversation so far
    (``[{"role": "user"|"assistant", "content": str}, ...]``, starting with a
    user turn). Returns the coach's reply text.
    """
    if not config.has_llm():
        raise RuntimeError(
            "No ANTHROPIC_API_KEY configured — set it in .env to enable the coach."
        )
    if not messages:
        raise ValueError("No messages to respond to — send at least one user turn.")

    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    # Judgment-heavy call → the full model (config.ANTHROPIC_MODEL), matching
    # how cover_letter routes its judgment call.
    msg = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=1024,
        system=coach_system(snapshot),
        messages=messages,
    )
    return "".join(b.text for b in msg.content if b.type == "text").strip()
