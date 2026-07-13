"""Offline tests for the Gmail API → gmail_sync transform boundary.

Feeds raw ``users.threads.get(format="full")``-shaped payloads through
``gmail_client.thread_to_record`` and on into the existing
``gmail_sync.normalize_thread``, asserting the two layers agree on shape:
header flattening, base64url body decoding, MIME-tree walking, SENT-label
handling, and date normalization. No network, no DB writes.

Run either way:
    python -m tests.test_gmail_client     # plain script, no pytest needed
    python -m pytest tests/               # if pytest is installed
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from job_bot.gmail_client import message_to_record, thread_to_record  # noqa: E402
from job_bot.gmail_sync import normalize_thread  # noqa: E402


def _b64(text: str) -> str:
    # Gmail uses unpadded base64url for body data.
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")


def _msg(sender: str, subject: str, date: str, body: str, *,
         labels: list[str] | None = None, to: str = "john@example.com",
         html: bool = False, msg_id: str = "m1") -> dict:
    """A minimal but faithful Gmail API message with a nested MIME tree."""
    mime = "text/html" if html else "text/plain"
    return {
        "id": msg_id,
        "threadId": "t1",
        "labelIds": labels or ["INBOX"],
        "snippet": body[:60],
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "From", "value": sender},
                {"name": "To", "value": to},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": date},
            ],
            "body": {"size": 0},
            "parts": [
                {"mimeType": mime, "body": {"data": _b64(body)}},
            ],
        },
    }


def test_message_flattening():
    rec = message_to_record(_msg(
        "Deloitte Talent <talent@deloitte.com>", "Interview invitation",
        "Tue, 07 Jul 2026 14:03:22 -0400",
        "We would like to invite you to interview for the IT Risk role.",
    ))
    assert rec["from"] == "Deloitte Talent <talent@deloitte.com>"
    assert rec["subject"] == "Interview invitation"
    assert rec["plaintextBody"].startswith("We would like to invite you")
    assert rec["labelIds"] == ["INBOX"]
    assert rec["toRecipients"] == ["john@example.com"]
    print("ok: message flattening")


def test_nested_multipart_and_html_fallback():
    # Deeply nested tree with only an HTML part — should strip tags.
    msg = {
        "id": "m9", "labelIds": ["INBOX"], "snippet": "snip",
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [{"name": "From", "value": "a@b.com"},
                        {"name": "Subject", "value": "S"}],
            "parts": [{
                "mimeType": "multipart/alternative",
                "parts": [{
                    "mimeType": "text/html",
                    "body": {"data": _b64(
                        "<html><style>p{}</style><body><p>Hello <b>John</b>,"
                        "</p><p>next steps</p></body></html>")},
                }],
            }],
        },
    }
    rec = message_to_record(msg)
    assert "<" not in rec["plaintextBody"]
    assert "Hello John" in rec["plaintextBody"].replace("  ", " ")
    assert "next steps" in rec["plaintextBody"]
    print("ok: nested multipart + html fallback")


def test_thread_to_normalized_record():
    """Full boundary: API thread → thread_to_record → normalize_thread."""
    thread = {
        "id": "thread-abc123",
        "snippet": "We received your application",
        "messages": [_msg(
            "KPMG Careers <noreply@kpmgcareers.com>",
            "Thank you for applying to KPMG",
            "Mon, 06 Jul 2026 09:15:00 +0000",
            "Thank you for applying. Our recruiting team will review.",
        )],
    }
    email = normalize_thread(thread_to_record(thread))
    assert email["gmail_id"] == "thread-abc123"
    assert email["sender"] == "KPMG Careers <noreply@kpmgcareers.com>"
    assert email["subject"] == "Thank you for applying to KPMG"
    assert email["received_at"] == "2026-07-06"  # RFC 2822 → ISO date
    assert "review" in email["body"]
    print("ok: thread -> normalize_thread")


def test_outbound_reply_ignored_for_status():
    """A thread ending in John's SENT reply must classify off the recruiter's
    last inbound message, not the reply."""
    thread = {
        "id": "t-conv",
        "messages": [
            _msg("Recruiter <r@ey.com>", "EY phone screen",
                 "Wed, 01 Jul 2026 10:00:00 +0000",
                 "We'd like to schedule a phone screen with you.", msg_id="m1"),
            _msg("John Bae <john@example.com>", "Re: EY phone screen",
                 "Wed, 01 Jul 2026 11:00:00 +0000",
                 "Sounds great, I'm available Thursday.",
                 labels=["SENT"], to="r@ey.com", msg_id="m2"),
        ],
    }
    email = normalize_thread(thread_to_record(thread))
    assert email["sender"] == "Recruiter <r@ey.com>"
    assert "phone screen" in email["body"]
    # Both parties still appear for company detection.
    assert "r@ey.com" in email["participants"]
    print("ok: outbound reply ignored for status")


def test_empty_and_missing_fields_are_safe():
    assert thread_to_record({}) == {"id": "", "subject": "", "snippet": "",
                                    "messages": []}
    rec = message_to_record({"id": "x", "payload": {}})
    assert rec["plaintextBody"] == "" and rec["subject"] == ""
    # Corrupt base64 must not raise.
    bad = {"id": "y", "payload": {"mimeType": "text/plain",
                                  "headers": [],
                                  "body": {"data": "!!!not-base64!!!"}}}
    assert message_to_record(bad)["plaintextBody"] == ""
    print("ok: defensive on empty/corrupt input")


if __name__ == "__main__":
    test_message_flattening()
    test_nested_multipart_and_html_fallback()
    test_thread_to_normalized_record()
    test_outbound_reply_ignored_for_status()
    test_empty_and_missing_fields_are_safe()
    print("\nall gmail_client transform tests passed")
