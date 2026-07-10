"""Tests for the intake module (manual job logging)."""

import pytest
from job_bot import intake, applications
from job_bot.db import connect


@pytest.fixture(autouse=True)
def _clean_db(tmp_path, monkeypatch):
    """Use a temporary database for each test."""
    from job_bot import config
    test_db = tmp_path / "test_job_bot.db"
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("job_bot.db.DB_PATH", test_db)
    yield


def test_log_job_basic():
    """Test basic job logging."""
    result = intake.log_job(
        url="https://example.com/job1",
        company_name="KPMG",
        title="Senior Auditor",
        portal="linkedin",
        status="applied"
    )

    assert result["id"] > 0
    assert result["company_name"] == "KPMG"
    assert result["job_title"] == "Senior Auditor"
    assert result["portal"] == "linkedin"
    assert result["status"] == "applied"


def test_log_job_creates_company():
    """Test that log_job creates a new company if it doesn't exist."""
    from job_bot import companies

    result = intake.log_job(
        url="https://example.com/job2",
        company_name="Goldman Sachs",
        title="Internal Auditor"
    )

    # Verify company was created
    company = companies.get_by_name_normalized("Goldman Sachs")
    assert company is not None
    assert company["id"] == result["company_id"]


def test_log_job_uses_existing_company():
    """Test that log_job links to existing company."""
    from job_bot import companies

    # Create a company first
    company, _ = companies.get_or_create("Deloitte", tier="Big4")

    # Log a job for that company
    result = intake.log_job(
        url="https://example.com/job3",
        company_name="Deloitte",
        title="Audit Manager"
    )

    assert result["company_id"] == company["id"]


def test_log_job_invalid_url():
    """Test that log_job rejects empty URL."""
    with pytest.raises(ValueError, match="URL is required"):
        intake.log_job(url="", company_name="KPMG", title="Auditor")


def test_log_job_invalid_company():
    """Test that log_job rejects invalid company names."""
    with pytest.raises(ValueError):
        intake.log_job(
            url="https://example.com/job",
            company_name="",
            title="Auditor"
        )


def test_log_job_invalid_portal():
    """Test that log_job rejects invalid portal."""
    with pytest.raises(ValueError, match="Invalid portal"):
        intake.log_job(
            url="https://example.com/job",
            company_name="KPMG",
            title="Auditor",
            portal="invalid_portal"
        )


def test_log_job_invalid_status():
    """Test that log_job rejects invalid status."""
    with pytest.raises(ValueError, match="Invalid status"):
        intake.log_job(
            url="https://example.com/job",
            company_name="KPMG",
            title="Auditor",
            status="invalid_status"
        )


def test_log_job_appears_in_applications():
    """Test that logged job appears in applications.build_applications()."""
    result = intake.log_job(
        url="https://example.com/job4",
        company_name="EY",
        title="IT Auditor"
    )

    apps = applications.build_applications()
    ey_app = next((a for a in apps if "EY" in a["company"]), None)
    assert ey_app is not None
    assert "IT Auditor" in ey_app["roles"]


def test_log_job_all_portals():
    """Test that all valid portals are accepted."""
    for portal in intake.VALID_PORTALS:
        result = intake.log_job(
            url=f"https://example.com/{portal}",
            company_name="PwC",
            title="Analyst",
            portal=portal
        )
        assert result["portal"] == portal


def test_log_job_all_statuses():
    """Test that all valid statuses are accepted."""
    for i, status in enumerate(intake.VALID_STATUSES):
        result = intake.log_job(
            url=f"https://example.com/job_status_{i}",
            company_name="Grant Thornton",
            title="Associate",
            status=status
        )
        assert result["status"] == status


def test_log_job_name_normalization():
    """Test that company names are normalized to canonical form."""
    # Multiple variations should map to the same canonical name
    result1 = intake.log_job(
        url="https://example.com/a",
        company_name="KPMG USA",
        title="Auditor"
    )

    result2 = intake.log_job(
        url="https://example.com/b",
        company_name="kpmg",
        title="Senior Auditor"
    )

    assert result1["company_name"] == result2["company_name"]
    assert result1["company_id"] == result2["company_id"]
