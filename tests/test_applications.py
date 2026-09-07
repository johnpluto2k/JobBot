"""Funnel reconciliation rules in job_bot.applications.

Regressions caught on 2026-09-07:
  * A lone `recruiter_reply` email (a Coinbase newsletter, an IBM event RSVP)
    was enough to put a company in the funnel as an application.
  * A rejection anywhere in a company's history hid a later application
    (Robinhood: rejected Nov 2025, re-applied Sept 2026, shown as Rejected).
"""

from datetime import date

import pytest

from job_bot import applications
from job_bot.db import connect


@pytest.fixture(autouse=True)
def _clean_db(tmp_path, monkeypatch):
    from job_bot import config
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("job_bot.db.DB_PATH", tmp_path / "t.db")
    yield


REF = date(2026, 9, 7)


def _email(company, category, received_at, subject):
    con = connect()
    con.execute("INSERT INTO tracked_emails (received_at, sender, subject, company, category) "
                "VALUES (?,?,?,?,?)", (received_at, "x@example.com", subject, company, category))
    con.commit()
    con.close()


def _job(company, title, site, status, date_posted, url=None):
    con = connect()
    con.execute("INSERT INTO jobs (company, title, site, status, date_posted, url) "
                "VALUES (?,?,?,?,?,?)", (company, title, site, status, date_posted, url))
    con.commit()
    con.close()


def _rejection(company, rejected_on):
    con = connect()
    con.execute("INSERT INTO rejections (company, rejected_on, source) VALUES (?,?,'inbox')",
                (company, rejected_on))
    con.commit()
    con.close()


def _status(company):
    return {a["company"]: a for a in applications.build_applications(REF)}.get(company)


def test_newsletter_tagged_recruiter_reply_is_not_an_application():
    _email("Coinbase", "recruiter_reply", "2026-09-02",
           "Bitcoin just had its best month in a year. What's next?")
    _email("Ibm", "recruiter_reply", "2026-09-07",
           "Registration Confirmation for The Consulting Edge: Shape What's Next")
    assert _status("Coinbase") is None
    assert _status("Ibm") is None


def test_application_confirmation_email_counts():
    _email("Robinhood", "recruiter_reply", "2026-09-07", "Thank you for applying to Robinhood")
    a = _status("Robinhood")
    assert a and a["status"] == "in_review"


def test_recruiter_reply_counts_when_a_job_row_exists():
    _job("Deloitte", "Audit Intern", "tracker", "applied", "2026-09-01")
    _email("Deloitte", "recruiter_reply", "2026-09-03", "Following up on next steps")
    a = _status("Deloitte")
    assert a and a["status"] == "in_review" and a["emails"] == 1


def test_strong_signals_still_prove_an_application():
    _email("KPMG", "interview_invite", "2026-09-01", "Invitation to interview")
    _email("PwC", "rejection", "2026-09-01", "Update on your application")
    assert _status("KPMG")["status"] == "interviewing"
    assert _status("PwC")["status"] == "rejected"


def test_reapplying_after_a_dated_rejection_starts_a_new_cycle():
    # Old cycle: applied Oct 2025, rejected Nov 2025.
    _email("Robinhood", "recruiter_reply", "2025-10-15", "Thank you for applying to Robinhood")
    _email("Robinhood", "rejection", "2025-11-12",
           "Important information about your application to Robinhood")
    _rejection("Robinhood", "2025-11-12")
    _job("Robinhood", "Financial Reporting Intern - Summer 2026", "ledger", "rejected", "2026-02-15")
    assert _status("Robinhood")["status"] == "rejected"

    # New cycle: logged through intake today + confirmation email.
    _job("Robinhood", "Business Analyst (New Grad)", "tracker", "applied", "2026-09-07",
         url="https://boards.greenhouse.io/robinhood/jobs/1")
    _email("Robinhood", "recruiter_reply", "2026-09-07", "Thank you for applying to Robinhood")
    a = _status("Robinhood")
    assert a["status"] == "in_review"
    assert a["reapplied"] is True
    assert a["positions"] == 2  # history is kept, not erased


def test_confirmation_email_alone_does_not_override_a_ledger_rejection():
    # Deloitte: the Feb-2026 "thank you for applying" receipts are the very
    # applications the ledger then marks rejected. Only a tracker-logged job
    # dated after the ledger snapshot can start a new cycle.
    _email("Deloitte", "rejection", "2025-12-12", "Deloitte Follow Up")
    _job("Deloitte", "Audit & Assurance Intern FSA - Summer 2027", "ledger", "rejected", "2026-02-15")
    _email("Deloitte", "recruiter_reply", "2026-02-16", "Thank you for applying to Deloitte!")
    a = _status("Deloitte")
    assert a["status"] == "rejected"
    assert a["reapplied"] is False


def test_rejection_after_reapplying_is_a_rejection_again():
    _rejection("Amazon", "2025-11-01")
    _job("Amazon", "BA", "tracker", "applied", "2026-09-01")
    assert _status("Amazon")["status"] == "in_review"
    _email("Amazon", "rejection", "2026-09-05", "Your application")
    assert _status("Amazon")["status"] == "rejected"


def test_undated_rejection_stays_sticky():
    _rejection("Meta", None)
    _job("Meta", "Analyst", "tracker", "applied", "2026-09-01")
    assert _status("Meta")["status"] == "rejected"
