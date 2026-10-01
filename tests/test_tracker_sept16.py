"""Applications-tracker regressions caught on 2026-09-16.

Against the real inbox, 4 of ~15 applications sent since Sept 7 reached the
tracker:
  * three Mastercard receipts in one Gmail thread counted as one (and with no
    company, as zero) because only the thread's latest message was read;
  * IBM's "Action Required: IBM Assessments for completion" was a rejection,
    a Deloitte recruiter's "Unfortunately I can't meet one on one" was a
    rejection, and KPMG's "KPMG Application - <role>" receipt an interview;
  * BlackRock (via blackrock.tal.net) was filed as "Tal", Mastercard promos as
    "Block";
  * a rejection anywhere at a company hid every newer application there
    (KPMG, Deloitte), and one rejected position closed the others.
"""

from datetime import date

import pytest

from job_bot import applications, inbox, intake
from job_bot.db import connect
from job_bot.gmail_sync import expand_thread


@pytest.fixture(autouse=True)
def _clean_db(tmp_path, monkeypatch):
    from job_bot import config
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "TRACKER_SINCE", "")
    monkeypatch.setattr("job_bot.db.DB_PATH", tmp_path / "t.db")
    yield


REF = date(2026, 9, 16)

# --- classification -------------------------------------------------------------


def test_assessment_subject_beats_body_fine_print():
    r = inbox.classify_email(
        "Action Required:IBM Assessments for completion Alex Doe - 130070 Integration Strategy Consultant",
        "Thank you for applying to the 130070 Integration Strategy Consultant - 2027 Full Time ELH "
        "position. You're invited to complete IBM's recorded assessment. Candidates who do not meet "
        "the deadline will not be considered.",
        "IBM Talent Acquisition <talent@ibm.com>")
    assert r["category"] == "assessment"
    assert r["company"] == "IBM"
    assert r["applied"] is True


def test_human_unfortunately_is_not_a_rejection():
    r = inbox.classify_email(
        "RE: Thank you for organizing Thursday's GPS event",
        "Hi Alex,\n\nUnfortunately I am not able to meet one on one with students given the large "
        "volume of requests I get.\n\nOn Mon, Sep 14, 2026 Alex wrote:\n> not moving forward",
        "Recruiter, Campus <campus.recruiter@deloitte.com>")
    assert r["category"] != "rejection"


def test_unfortunately_about_an_application_is_still_a_rejection():
    r = inbox.classify_email("Your application", "Unfortunately, your application was not successful.",
                             "no-reply@acme.com")
    assert r["category"] == "rejection"


def test_receipt_saying_looks_forward_to_speaking_is_not_an_interview():
    r = inbox.classify_email(
        "KPMG Application - Technology Assurance Associate | New York Summer/Fall 2027 position, Job #137522",
        "Congratulations on applying for the Technology Assurance Associate position with KPMG! "
        "Your application is now complete. Our team looks forward to speaking with you.",
        "kpmg@avature.net")
    assert r["category"] == "recruiter_reply"
    assert r["applied"] is True
    assert r["company"] == "KPMG"
    assert r["role"].startswith("Technology Assurance Associate")


def test_auto_reply_is_noise():
    assert inbox.is_noise("Automatic reply: Applied to EY McLean", "I'm out of office", "x@ey.com")


def test_ats_subdomain_names_the_employer():
    assert inbox.detect_company("update", "noreply@blackrock.tal.net", subject="Application update") == "BlackRock"
    assert inbox.detect_company("", "no-reply@afs.com", subject="Hi") == "Accenture Federal Services"


def test_common_word_employer_needs_subject_or_sender():
    assert inbox.detect_company("Block time on your calendar to explore jobs",
                                "Mastercard <talent@careers.mastercard.com>",
                                subject="Start exploring job opportunities") == "Mastercard"
    assert inbox.detect_company("block your calendar", "someone@example.org", subject="Hello") != "Block"


@pytest.mark.parametrize("subject,body,role", [
    ("Thank you for your application!",
     "We have received your application for the role: Technology Risk Analyst I, Launch Program 2027 "
     "– St. Louis, MO, US . At Mastercard, our people", "Technology Risk Analyst I, Launch Program 2027 "
     "– St. Louis, MO, US"),
    ("Morgan Stanley Application Update",
     "Thank you for applying to the 2027 Internal Audit - Business Audit Summer Analyst Program "
     "(Baltimore) at Morgan Stanley.", "Internal Audit - Business Audit Summer Analyst Program (Baltimore)"),
    ("Thank you for applying to Deloitte!",
     "Thank you for submitting an application for the position of Consultative Offerings - Analyst - "
     "Technology Transformation, 350487. You can view", "Consultative Offerings - Analyst - Technology Transformation"),
    ("Your IBM Application: Next Steps", "We are excited to see that you have applied", None),
])
def test_role_extraction(subject, body, role):
    assert inbox.extract_role(subject, body) == role


def test_same_role():
    assert inbox.same_role("USA - Consulting - Technology Consulting - Staff (Req 1741471)",
                           "USA - Consulting - Technology Consulting - Staff")
    assert not inbox.same_role("Audit Intern (126116)", "Audit Intern (126095)")
    assert not inbox.same_role("Business Analyst (New Grad)", "Technology Operations Intern")


# --- thread expansion ------------------------------------------------------------


def _m(mid, subject, body, date_, labels=("INBOX",)):
    return {"id": mid, "from": "mastercard@myworkday.com", "subject": subject, "date": date_,
            "plaintextBody": body, "labelIds": list(labels)}


def test_every_receipt_in_a_thread_becomes_a_record():
    thread = {"id": "T1", "subject": "Thank you for your application!", "messages": [
        _m("T1", "Thank you for your application!",
           "We have received your application for the role: Associate Consultant (DC)",
           "Wed, 16 Sep 2026 01:03:14 +0000"),
        _m("M2", "Thank you for your application!",
           "We have received your application for the role: Technology Risk Analyst I (MO)",
           "Wed, 16 Sep 2026 01:14:45 +0000"),
        _m("M3", "Thank you for your application!",
           "We have received your application for the role: Program Management Analyst I (MO)",
           "Wed, 16 Sep 2026 01:20:29 +0000"),
    ]}
    recs = expand_thread(thread)
    assert [r["gmail_id"] for r in recs] == ["T1", "T1:T1", "T1:M2"]
    assert all(r["received_at"] == "2026-09-16" for r in recs)
    for r in recs:
        inbox.record_email(r["received_at"], r["sender"], r["subject"], r["body"], r["gmail_id"])
    a = {x["company"]: x for x in applications.build_applications(REF)}["Mastercard"]
    assert a["positions"] == 3 and a["status"] == "in_review"


def test_date_without_weekday_parses():
    from job_bot.gmail_sync import _norm_date
    assert _norm_date("16 Sep 2026 02:35:36 +0000") == "2026-09-16"


# --- funnel ------------------------------------------------------------------------


def _email(company, category, received_at, subject, role=None, applied=0):
    con = connect()
    con.execute("INSERT INTO tracked_emails (received_at, sender, subject, company, category, role, applied) "
                "VALUES (?,?,?,?,?,?,?)", (received_at, "x@example.com", subject, company, category, role, applied))
    con.commit()
    con.close()


def _job(company, title, site, status, date_posted, url=None):
    con = connect()
    cur = con.execute("INSERT INTO jobs (company, title, site, status, date_posted, url) VALUES (?,?,?,?,?,?)",
                      (company, title, site, status, date_posted, url or f"u://{company}/{title}"))
    con.commit()
    jid = cur.lastrowid
    con.close()
    return jid


def _get(company, **kw):
    return {a["company"]: a for a in applications.build_applications(REF, **kw)}.get(company)


def test_receipt_months_after_the_ledger_starts_a_new_cycle():
    # KPMG: ledger rejections (Feb import) + a March rejection, then a Sept receipt.
    _job("KPMG", "Tax Intern - Tempe Summer 2027", "ledger", "rejected", "2026-02-15")
    _email("KPMG", "rejection", "2026-03-04", "Tax Intern – Tempe Summer 2027")
    _email("KPMG", "recruiter_reply", "2026-09-16", "KPMG Application - Technology Assurance Associate",
           role="Technology Assurance Associate", applied=1)
    a = _get("KPMG")
    assert a["status"] == "in_review" and a["reapplied"] is True
    assert a["open_positions"] == 1


def test_role_named_rejection_only_closes_that_role():
    _job("BlackRock", "2027 Analyst Program", "tracker", "applied", "2026-09-01")
    _email("BlackRock", "rejection", "2026-09-04", "BlackRock | Application update",
           role="2026 Summer Internship Program - Technology Operations")
    assert _get("BlackRock")["status"] == "in_review"


def test_rejecting_one_logged_position_keeps_the_others_open():
    j1 = _job("EY", "Technology Consulting Staff", "tracker", "applied", "2026-09-08")
    _job("EY", "Assurance Audit Analyst", "tracker", "applied", "2026-09-08")
    intake.set_status(j1, "rejected")
    a = _get("EY")
    assert a["status"] == "in_review"
    assert {p["status"] for p in a["positions_detail"]} == {"applied", "rejected"}


def test_all_positions_rejected_is_rejected():
    j1 = _job("EY", "Technology Consulting Staff", "tracker", "applied", "2026-09-08")
    intake.set_status(j1, "rejected")
    assert _get("EY")["status"] == "rejected"


def test_logged_interview_counts_as_interviewing():
    _job("Morgan Stanley", "Internal Audit Summer Analyst", "tracker", "interview", "2026-09-07")
    assert _get("Morgan Stanley")["status"] == "interviewing"


def test_receipt_attaches_to_the_logged_position():
    _job("Robinhood", "Business Analyst (New Grad)", "tracker", "applied", "2026-09-07")
    _email("Robinhood", "recruiter_reply", "2026-09-07", "Thank you for applying to Robinhood", applied=1)
    assert _get("Robinhood")["positions"] == 1


def test_season_filter_drops_old_cycles():
    _job("PwC", "Audit Intern - Summer 2026", "ledger", "rejected", "2026-02-15")
    _email("PwC", "rejection", "2025-09-24", "Audit Intern – Summer 2027")
    _email("BlackRock", "rejection", "2026-09-04", "BlackRock | Application update")
    _email("Mastercard", "recruiter_reply", "2026-09-16", "Thank you for your application!", applied=1)
    apps = {a["company"] for a in applications.build_applications(REF, since="2026-07-01")}
    assert apps == {"Mastercard"}  # a lone in-season rejection is about an old application
    assert {"PwC", "BlackRock", "Mastercard"} <= {a["company"] for a in applications.build_applications(REF, since="")}


def test_hidden_company_leaves_the_tracker():
    _email("Sumter Advertising", "interview_invite", "2026-09-07", "Invitation to Interview")
    assert _get("Sumter Advertising")
    intake.set_hidden("Sumter Advertising")
    assert _get("Sumter Advertising") is None
    assert intake.list_hidden() == ["Sumter Advertising"]
    intake.set_hidden("Sumter Advertising", False)
    assert _get("Sumter Advertising")


def test_set_status_refuses_imported_rows():
    jid = _job("PwC", "Audit Intern", "ledger", "rejected", "2026-02-15")
    with pytest.raises(ValueError):
        intake.set_status(jid, "applied")


def test_relogging_keeps_the_original_date():
    r = intake.log_job("u://x", "Deloitte", "Analyst", applied_on="2026-09-14")
    intake.log_job("u://x", "Deloitte", "Analyst", status="interview")
    con = connect()
    d = con.execute("SELECT date_posted, status FROM jobs WHERE id=?", (r["id"],)).fetchone()
    con.close()
    assert tuple(d) == ("2026-09-14", "interview")


def test_password_footer_does_not_drop_a_receipt():
    body = ("Thank you for submitting an application for the position of Analyst - Finance Technology, "
            "360130.\n\nForgot your password? Reset your password here.")
    assert not inbox.is_noise("Thank you for applying to Deloitte!", body, "donotreply@deloitte.com")
    assert inbox.is_noise("Reset your password", "", "donotreply@deloitte.com")


def test_no_longer_being_considered_is_a_rejection():
    r = inbox.classify_email("Thank you for your interest in CBIZ",
                             "Thank you for your interest in the&nbsp;Tax Intern | Spring 2027 position at "
                             "CBIZ. You are no longer being considered for this position.",
                             "CBIZ Careers <noreply@cbiz.com>")
    assert r["category"] == "rejection"
    assert r["role"] == "Tax Intern | Spring 2027"


def test_same_program_different_titles_are_different_roles():
    assert not inbox.same_role("Program Management Analyst I, Launch Program 2027 – St. Louis, MO, US",
                               "Technology Risk Analyst I, Launch Program 2027 – St. Louis, MO, US")


def test_assessment_does_not_mark_a_logged_position_interviewing():
    jid = _job("EY", "Assurance Audit Analyst", "tracker", "applied", "2026-09-08")
    inbox.record_email("2026-09-08", "talentcentral@shl.com", "Action Required: Complete your EY skills assessment",
                       "To finish your application, please complete a mandatory skills assessment.", "g-ey")
    con = connect()
    assert con.execute("SELECT status FROM jobs WHERE id=?", (jid,)).fetchone()[0] == "applied"
    con.close()


def test_roleless_receipt_folds_into_same_day_named_receipt():
    _email("KPMG", "recruiter_reply", "2026-09-16", "Thank you for your interest in KPMG Audit", applied=1)
    _email("KPMG", "recruiter_reply", "2026-09-16", "KPMG Application - Technology Assurance Associate",
           role="Technology Assurance Associate", applied=1)
    assert _get("KPMG")["positions"] == 1
