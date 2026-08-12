"""Offline test for POST /api/tailor's no-LLM path.

Runs without any API key or network access: ANTHROPIC_API_KEY is monkeypatched
to empty so `config.has_llm()` is False end-to-end (heuristic JD parsing, no
LLM bullet rewrite, no LLM prose summary).
"""

import json

import pytest
from fastapi.testclient import TestClient

from job_bot import config, google_auth
from job_bot.api import app

_JD_TEXT = """
IT Audit Associate — Acme Corp

Location: Washington, DC (Hybrid)

We're looking for an IT Audit Associate to join our internal audit team.

Required:
- SQL
- Excel
- SOX compliance experience

Preferred:
- Python
- Data analytics

Bachelor's degree required. Minimum GPA 3.0. 0-2 years of experience.
"""

_PROFILE = {
    "personal": {
        "name": "John Bae",
        "email": "john@example.com",
        "phone": "555-555-5555",
        "location": "Washington, DC",
        "linkedin": "linkedin.com/in/johnbae",
    },
    "education": [
        {
            "school": "University of Maryland",
            "degree": "B.S. Accounting",
            "major": "Accounting",
            "secondary_major": "Information Science",
            "gpa": 3.8,
            "graduation_date": "May 2027",
            "relevant_coursework": ["Auditing", "Data Analytics"],
        }
    ],
    "experience": [
        {
            "role": "Audit Intern",
            "organization": "Test Firm",
            "location": "Washington, DC",
            "start_date": "Jun 2025",
            "end_date": "Aug 2025",
            "is_current": False,
            "bullets": [
                {
                    "text": "Performed SOX 404 testing across 3 control cycles",
                    "keyword_tags": ["SOX", "audit"],
                    "quantified": True,
                    "strength_score": 0.8,
                },
                {
                    "text": "Built SQL queries to sample transaction populations",
                    "keyword_tags": ["SQL"],
                    "quantified": False,
                    "strength_score": 0.6,
                },
            ],
        }
    ],
    "leadership": [],
    "projects": [],
    "skills": [
        {"category": "technical", "skills": ["Excel", "SQL", "Python"]},
    ],
    "targets": {
        "target_roles": ["IT Audit Associate"],
        "target_firms": [],
        "target_markets": [],
        "personas": [],
    },
    "certifications": [],
    "summary": "Accounting + IS student targeting IT audit roles.",
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Isolated OUTPUT_DIR/PROFILE_JSON, no API key, auth middleware bypassed."""
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "PROFILE_JSON", tmp_path / "master_profile.json")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")

    config.PROFILE_JSON.write_text(json.dumps(_PROFILE, indent=2), encoding="utf-8")

    # Single-user session gate isn't the concern of this test — bypass it.
    monkeypatch.setattr(google_auth, "session_valid", lambda cookie: True)

    return TestClient(app)


def test_tailor_no_llm_path(client):
    assert config.has_llm() is False

    resp = client.post("/api/tailor", json={"jd": _JD_TEXT})
    assert resp.status_code == 200

    data = resp.json()
    assert "error" not in data

    assert data["summary"]["prose"] is None
    assert isinstance(data["yaml"], str) and data["yaml"].strip() != ""
    # yaml is emitted as JSON text (valid YAML) — confirm it parses and has content.
    parsed_yaml = json.loads(data["yaml"])
    assert "cv" in parsed_yaml

    assert "field" in data and data["field"]
    assert data["suggested_renderer"] in ("rendercv", "docx")
