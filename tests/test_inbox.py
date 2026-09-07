"""Inbox classifier + tracker update rules in job_bot.inbox.

Regressions caught on 2026-09-07: a Coinbase Bytes newsletter and an IBM event
registration receipt were both filed as `recruiter_reply`, and a "thank you for
applying" receipt downgraded a tracker job from 'applied' to 'networking'.
"""

import pytest

from job_bot import inbox
from job_bot.db import connect


@pytest.fixture(autouse=True)
def _clean_db(tmp_path, monkeypatch):
    from job_bot import config
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("job_bot.db.DB_PATH", tmp_path / "t.db")
    yield


def test_newsletter_sender_is_noise_even_with_a_recruiting_word_in_the_body():
    r = inbox.classify_email(
        "Bitcoin just had its best month in a year. What's next?",
        "Let's connect. You applied for early access to Coinbase One.",
        "Coinbase Bytes <newsletter@mail.coinbase.com>",
    )
    assert r["category"] == "other"
    assert r["status_hint"] is None


def test_event_registration_receipt_is_noise():
    r = inbox.classify_email(
        "Registration Confirmation for The Consulting Edge: Shape What's Next",
        "Thanks for registering. Our talent acquisition team looks forward to seeing you.",
        "IBM Talent Acquisition <talent@ibm.com>",
    )
    assert r["category"] == "other"


def test_price_alerts_are_noise():
    r = inbox.classify_email("Price Alert: Dogecoin (DOGE) is Up 5.30%", "",
                             "Coinbase <no-reply@mail.coinbase.com>")
    assert r["category"] == "other"


def test_application_confirmation_is_still_a_recruiter_reply():
    r = inbox.classify_email("Thank you for applying to Robinhood",
                             "We received your application for Business Analyst (New Grad).",
                             "no-reply@robinhood.com")
    assert r["category"] == "recruiter_reply"
    assert r["company"] == "Robinhood"


def test_interview_invite_survives_an_event_word_in_the_body():
    r = inbox.classify_email(
        "Invitation to interview - Audit Intern",
        "We'd like to invite you to a virtual interview. Join our webinar on interview prep too.",
        "recruiter@kpmg.com",
    )
    assert r["category"] == "interview_invite"


def test_bare_connect_no_longer_triggers_recruiter_reply():
    r = inbox.classify_email("Coinbase Connect is live", "Connect your wallet today.", "info@example.com")
    assert r["category"] == "other"
    r = inbox.classify_email("Quick note", "I'd love to connect about the analyst role.", "jane@acme.com")
    assert r["category"] == "recruiter_reply"


def _job(company, status):
    con = connect()
    cur = con.execute("INSERT INTO jobs (company, title, site, status, date_posted, url) "
                      "VALUES (?,?,?,?,?,?)",
                      (company, "Analyst", "tracker", status, "2026-09-07", f"https://x/{company}/{status}"))
    con.commit()
    jid = cur.lastrowid
    con.close()
    return jid


def _status(jid):
    con = connect()
    s = con.execute("SELECT status FROM jobs WHERE id=?", (jid,)).fetchone()[0]
    con.close()
    return s


def test_confirmation_receipt_does_not_downgrade_applied_to_networking():
    jid = _job("Robinhood", "applied")
    inbox.record_email("2026-09-07", "no-reply@robinhood.com", "Thank you for applying to Robinhood",
                       "We received your application.", gmail_id="g1")
    assert _status(jid) == "applied"


def test_receipt_still_lifts_a_saved_job_to_networking():
    jid = _job("Robinhood", "saved")
    inbox.record_email("2026-09-07", "no-reply@robinhood.com", "Thank you for applying to Robinhood",
                       "", gmail_id="g2")
    assert _status(jid) == "networking"


def test_interview_invite_lifts_applied_to_interview_but_not_offer():
    applied = _job("KPMG", "applied")
    offer = _job("KPMG", "offer")
    inbox.record_email("2026-09-07", "recruiter@kpmg.com", "Invitation to interview",
                       "phone screen next week", gmail_id="g3")
    assert _status(applied) == "interview"
    assert _status(offer) == "offer"
