"""Gmail → tracker sync.

Turns Gmail thread/message records (as returned by the Gmail MCP's
`search_threads` / `get_thread`) into classified, deduped pipeline data:
interview invites, assessments, recruiter replies, rejections, and offers — each
advancing the matching application's status and auto-logging rejections.

The MCP call itself happens in the agent layer (it holds the OAuth session); this
module is the pure, testable transform + persistence so a scan is one step and
re-running never double-logs (dedupe is by Gmail id).

Expected per-thread shape (defensive — extra keys ignored):
    {"id": "<threadId>", "subject": "...", "from"/"sender": "...",
     "snippet"/"body": "...", "date"/"received_at": "...", "messages": [ ... ]}
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime

from .inbox import triage

ORDER = ["offer", "interview_invite", "assessment", "recruiter_reply", "rejection", "other"]
ICON = {"offer": "🎉", "interview_invite": "📅", "assessment": "📝",
        "recruiter_reply": "💬", "rejection": "❌", "other": "•"}


def _first(d: dict, *keys, default=""):
    for k in keys:
        v = d.get(k)
        if v:
            return v
    return default


def _norm_date(raw: str) -> str:
    """Best-effort normalize a Gmail date header to YYYY-MM-DD."""
    if not raw:
        return ""
    raw = str(raw).strip()
    # already ISO-ish
    m = re.match(r"(\d{4})[-/](\d{2})[-/](\d{2})", raw)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S",
                "%d %b %Y", "%b %d, %Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw[:31].strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw[:10]


def _is_outbound(msg: dict) -> bool:
    """True if this message was sent BY the user (so it reflects our outreach, not a status)."""
    labels = msg.get("labelIds") or msg.get("labels") or []
    return "SENT" in labels


def normalize_thread(thread: dict) -> dict:
    """Flatten one MCP thread record to the {received_at, sender, subject, body, gmail_id} shape.

    For a multi-message conversation we classify off the LATEST inbound (recruiter)
    message — that carries the current status — while detecting the company across
    every participant in the thread (so a reply John sent to `x@deloitte.com` still
    resolves to Deloitte). Falls back to the first/only message for single-shot mail.
    """
    msgs = thread.get("messages") or thread.get("relatedMessages") or []
    inbound = [m for m in msgs if not _is_outbound(m)]
    msg = (inbound[-1] if inbound else (msgs[-1] if msgs else thread))
    subject = _first(thread, "subject") or _first(msg, "subject")
    sender = _first(msg, "from", "sender", "From") or _first(thread, "from", "sender")
    body = _first(msg, "plaintextBody", "body", "snippet") or _first(thread, "snippet", "body")
    date = _first(msg, "date", "Date", "received_at", "internalDate") or _first(thread, "date")
    # Aggregate every address that appears in the thread to strengthen company detection.
    participants = []
    for m in (msgs or [thread]):
        participants.append(_first(m, "from", "sender", "From"))
        participants.extend(m.get("toRecipients") or [])
        participants.extend(m.get("ccRecipients") or [])
    return {
        "received_at": _norm_date(date),
        "sender": str(sender),
        "subject": str(subject),
        "body": str(body),
        "participants": " ".join(str(p) for p in participants if p),
        "gmail_id": str(thread.get("id") or thread.get("threadId") or msg.get("id") or ""),
    }


def sync_threads(threads: list[dict], drop_other: bool = True) -> dict:
    """Normalize, classify, persist, and summarize a batch of Gmail threads.

    Account-verification / password-reset / newsletter mail is filtered out
    before persistence so it never pollutes the tracker. With ``drop_other`` (the
    default for a wide sweep), signal-less mail from unknown senders is classified
    but not persisted — only real recruiting categories (or known employers) land
    in the tracker."""
    from .inbox import is_noise

    all_emails = [normalize_thread(t) for t in threads]
    emails = [e for e in all_emails if not is_noise(e["subject"], e["body"])]
    noise = len(all_emails) - len(emails)
    results = triage(emails, drop_other=drop_other)

    dropped = [r for r in results if r.get("dropped")]
    new = [r for r in results if not r.get("skipped")]
    skipped = [r for r in results if r.get("skipped") and not r.get("dropped")]
    by_cat = Counter(r["category"] for r in new)
    companies = Counter(r["company"] for r in new if r.get("company"))

    # Build per-category detail (newest first) for the report.
    detail: dict[str, list[dict]] = {c: [] for c in ORDER}
    for r in sorted(new, key=lambda x: x.get("received_at", ""), reverse=True):
        detail.setdefault(r["category"], []).append({
            "company": r.get("company"), "subject": r.get("subject", "")[:70],
            "date": r.get("received_at"), "action": r.get("action"),
        })
    return {
        "scanned": len(all_emails), "new": len(new), "skipped": len(skipped),
        "noise": noise, "dropped": len(dropped), "by_category": dict(by_cat),
        "companies": companies.most_common(), "detail": detail,
    }


def format_report(s: dict) -> str:
    lines = ["\n" + "=" * 66,
             f"GMAIL SCAN — {s['scanned']} threads ({s['new']} new, "
             f"{s['skipped']} already tracked, "
             f"{s.get('noise', 0) + s.get('dropped', 0)} noise/non-recruiting)",
             "=" * 66]
    if s["new"] == 0:
        lines.append("\nNo new recruiting emails to log.")
        return "\n".join(lines)
    counts = "  ".join(f"{ICON.get(c,'•')} {c}={n}" for c, n in
                       sorted(s["by_category"].items(), key=lambda kv: ORDER.index(kv[0])
                              if kv[0] in ORDER else 9))
    lines.append("\n" + counts)
    for cat in ORDER:
        rows = s["detail"].get(cat) or []
        if not rows:
            continue
        lines.append(f"\n{ICON.get(cat,'•')} {cat.upper().replace('_',' ')} ({len(rows)})")
        for r in rows[:25]:
            lines.append(f"   {r['date'] or '—':<11} {(r['company'] or '—')[:18]:<18} "
                         f"{r['subject']}")
    lines.append("=" * 66)
    return "\n".join(lines)
