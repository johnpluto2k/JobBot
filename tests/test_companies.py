"""Tests for the companies module."""

import pytest
from datetime import date, timedelta

from job_bot import companies
from job_bot.db import connect


@pytest.fixture(autouse=True)
def _clean_db(tmp_path, monkeypatch):
    """Use a temporary database for each test."""
    from job_bot import config
    test_db = tmp_path / "test_job_bot.db"
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("job_bot.db.DB_PATH", test_db)
    yield
    # Cleanup happens automatically when tmp_path is destroyed


def test_insert_basic():
    """Test basic insert operation."""
    company_id = companies.insert("Deloitte", tier="Big4")
    assert company_id > 0

    company = companies.get_by_id(company_id)
    assert company is not None
    assert company["name"] == "Deloitte"
    assert company["name_normalized"] == "Deloitte"
    assert company["tier"] == "Big4"


def test_get_or_create_new():
    """Test get_or_create for a new company."""
    company, created = companies.get_or_create("KPMG")
    assert created is True
    assert company["name_normalized"] == "KPMG"
    assert company["tier"] == "other"  # default


def test_get_or_create_existing():
    """Test get_or_create returns existing company without creating duplicate."""
    company1, created1 = companies.get_or_create("PwC", tier="Big4")
    assert created1 is True

    company2, created2 = companies.get_or_create("PwC")
    assert created2 is False
    assert company1["id"] == company2["id"]


def test_get_or_create_name_normalization():
    """Test that get_or_create uses canonical names."""
    company1, _ = companies.get_or_create("KPMG USA")
    company2, _ = companies.get_or_create("kpmg")
    assert company1["id"] == company2["id"]


def test_list_all():
    """Test listing all companies."""
    companies.insert("Deloitte", tier="Big4")
    companies.insert("EY", tier="Big4")
    companies.insert("Grant Thornton", tier="mid-tier")

    all_companies = companies.list_all()
    assert len(all_companies) == 3


def test_due_for_check():
    """Test due_for_check() returns companies past their next_check_due."""
    con = connect()
    try:
        # Create a company that's due (next_check_due is in the past)
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        con.execute("""
            INSERT INTO companies
            (name, name_normalized, next_check_due, tier)
            VALUES (?, ?, ?, ?)
        """, ("Company A", "Company A", yesterday, "other"))

        con.execute("""
            INSERT INTO companies
            (name, name_normalized, next_check_due, tier)
            VALUES (?, ?, ?, ?)
        """, ("Company B", "Company B", tomorrow, "other"))

        con.commit()

        due = companies.due_for_check()
        assert len(due) == 1
        assert due[0]["name"] == "Company A"
    finally:
        con.close()


def test_mark_checked():
    """Test mark_checked() updates last_checked and next_check_due."""
    company_id = companies.insert("Deloitte")

    today = date.today().isoformat()
    expected_next = (date.today() + timedelta(days=7)).isoformat()

    result = companies.mark_checked(company_id)
    assert result["last_checked"] == today
    assert result["next_check_due"] == expected_next


def test_mark_checked_custom_days():
    """Test mark_checked() with custom next_check_in_days."""
    company_id = companies.insert("KPMG")

    expected_next = (date.today() + timedelta(days=14)).isoformat()

    result = companies.mark_checked(company_id, next_check_in_days=14)
    assert result["next_check_due"] == expected_next


def test_update():
    """Test update() modifies company fields."""
    company_id = companies.insert("Goldman Sachs", tier="Big4")

    result = companies.update(company_id, notes="Active target")
    assert result["notes"] == "Active target"
    assert result["tier"] == "Big4"  # unchanged


def test_update_with_lists():
    """Test update() with portals and target_fields."""
    company_id = companies.insert("JPMorgan")

    result = companies.update(
        company_id,
        portals=["Indeed", "LinkedIn"],
        target_fields=["Finance / FP&A", "Internal Audit"]
    )

    import json
    assert json.loads(result["portals"]) == ["Indeed", "LinkedIn"]
    assert json.loads(result["target_fields"]) == ["Finance / FP&A", "Internal Audit"]


def test_match_key_treats_legal_suffixes_as_the_same_employer():
    """KPMG / kpmg / KPMG LLP / KPMG USA are one firm, and used to be four rows.

    canon() only rewrites a name when the WHOLE string is a known alias, so each
    spelling produced a different name_normalized and therefore its own tracker
    entry.
    """
    from job_bot.companies import match_key

    for variant in ("kpmg", "KPMG LLP", "KPMG USA", "KPMG, LLP"):
        assert match_key(variant) == match_key("KPMG"), variant
    assert match_key("Ernst & Young LLP") == match_key("Ernst & Young")


def test_match_key_keeps_genuinely_different_organizations_apart():
    """The loose key must not over-merge. Every pair below is two real, separate
    organizations that share a leading word."""
    from job_bot.companies import match_key

    for a, b in [("Accenture", "Accenture Federal Services"),
                 ("Federal Reserve Bank", "Federal Reserve Board"),
                 ("Kearney", "Kearney & Company"),
                 ("CACI", "CACI International")]:
        assert match_key(a) != match_key(b), f"{a} wrongly merged with {b}"


def test_get_or_create_matches_across_spellings():
    a, created_a = companies.get_or_create("KPMG LLP")
    b, created_b = companies.get_or_create("kpmg")
    assert created_a is True and created_b is False
    assert a["id"] == b["id"]

    other, created_other = companies.get_or_create("Kearney & Company")
    assert created_other is True
    assert other["id"] != a["id"]
