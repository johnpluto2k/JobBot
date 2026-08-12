"""Offline test for the Resume Studio JD-driven generation endpoints.

Runs without any API key or network access: ANTHROPIC_API_KEY is monkeypatched
to empty so `config.has_llm()` is False end-to-end. Unlike test_api_tailor.py
(which exercises the ephemeral scratch-render path), this exercises the real
Phase-4 pipeline (job_bot.generate.run_generate) that saves a full application
folder to disk and records it in the `generated_resumes` table — so the
pipeline itself is not mocked, only the LLM is disabled.
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
    """Isolated OUTPUT_DIR/PROFILE_JSON (and therefore isolated job_bot.db),
    no API key, auth middleware bypassed — mirrors test_api_tailor.py."""
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "PROFILE_JSON", tmp_path / "master_profile.json")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")

    config.PROFILE_JSON.write_text(json.dumps(_PROFILE, indent=2), encoding="utf-8")

    # Single-user session gate isn't the concern of this test — bypass it.
    monkeypatch.setattr(google_auth, "session_valid", lambda cookie: True)

    return TestClient(app)


def test_studio_generate_history_and_file(client):
    assert config.has_llm() is False

    # --- POST /api/studio/generate: runs the real Phase-4 pipeline ---
    resp = client.post("/api/studio/generate", json={"jd_text": _JD_TEXT})
    assert resp.status_code == 200
    data = resp.json()
    assert "error" not in data, data

    summary = data["summary"]
    assert isinstance(summary["ats_before"], (int, float))
    assert isinstance(summary["ats_after"], (int, float))

    resume_files = data["resume_files"]
    assert "pdf" in resume_files["kinds"]
    assert "docx" in resume_files["kinds"]
    row_id = resume_files["id"]
    assert isinstance(row_id, int)

    folder = data["history_row"]["folder_path"]
    app_dir = config.OUTPUT_DIR / "applications" / folder
    assert (app_dir / "resume.pdf").is_file()
    assert (app_dir / "resume.docx").is_file()

    # --- GET /api/studio/history: the run appears ---
    resp = client.get("/api/studio/history")
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert any(r["id"] == row_id for r in rows)
    row = next(r for r in rows if r["id"] == row_id)
    assert "pdf" in row["kinds"]
    assert "docx" in row["kinds"]

    # --- GET /api/studio/file: downloads the PDF ---
    resp = client.get(f"/api/studio/file?id={row_id}&kind=pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 1000

    # --- GET /api/studio/file: unknown row / kind soft-error as 404 JSON ---
    resp = client.get(f"/api/studio/file?id=999999&kind=pdf")
    assert resp.status_code == 404
    assert "error" in resp.json()

    resp = client.get(f"/api/studio/file?id={row_id}&kind=bogus")
    assert resp.status_code == 404
    assert "error" in resp.json()
