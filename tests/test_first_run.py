"""What a new user meets first: the dashboard without Google, and the demo.

Local mode opens the API without a session when no Google client is configured,
so the checks that matter are the ones that keep it closed: a caller from
another machine, a spoofed Host header, and any install that does have a client.
"""

import pytest
from fastapi.testclient import TestClient

from job_bot import config, db, demo, google_auth
from job_bot.api import app


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "PROFILE_JSON", tmp_path / "master_profile.json")
    monkeypatch.setattr(config, "TRACKER_SINCE", "")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "job_bot.db")
    monkeypatch.setattr("job_bot.api.DB_PATH", tmp_path / "job_bot.db")
    monkeypatch.setattr(google_auth, "SESSION_PATH", tmp_path / "app_session.json")
    return tmp_path


def _client(host: str = "127.0.0.1", base: str = "http://localhost:8000") -> TestClient:
    return TestClient(app, client=(host, 50000), base_url=base)


def _unconfigured(monkeypatch):
    monkeypatch.setattr(google_auth, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(google_auth, "GOOGLE_CLIENT_SECRET", "")


def test_local_mode_opens_dashboard_without_google(store, monkeypatch):
    _unconfigured(monkeypatch)
    c = _client()
    status = c.get("/api/auth/status").json()
    assert status == {"logged_in": True, "email": None, "configured": False, "local_mode": True}
    assert c.get("/api/summary").status_code == 200


def test_local_mode_is_loopback_only(store, monkeypatch):
    _unconfigured(monkeypatch)
    other_machine = _client(host="192.168.1.50")
    assert other_machine.get("/api/summary").status_code == 401
    assert other_machine.get("/api/auth/status").json()["logged_in"] is False


@pytest.mark.parametrize("host", ["evil.example", "evil.example:8000", "localhost.evil.example"])
def test_local_mode_rejects_foreign_host_header(store, monkeypatch, host):
    """DNS rebinding: a page on another domain that resolves to 127.0.0.1."""
    _unconfigured(monkeypatch)
    assert _client().get("/api/summary", headers={"host": host}).status_code == 401


@pytest.mark.parametrize("host", ["localhost", "localhost:8000", "127.0.0.1:8000", "[::1]:8000", "[::1]"])
def test_local_mode_accepts_every_loopback_spelling(store, monkeypatch, host):
    _unconfigured(monkeypatch)
    assert _client().get("/api/summary", headers={"host": host}).status_code == 200


def test_configured_install_still_requires_sign_in(store, monkeypatch):
    monkeypatch.setattr(google_auth, "GOOGLE_CLIENT_ID", "id")
    monkeypatch.setattr(google_auth, "GOOGLE_CLIENT_SECRET", "secret")
    c = _client()
    assert c.get("/api/summary").status_code == 401
    assert c.get("/api/auth/status").json() == {
        "logged_in": False, "email": None, "configured": True, "local_mode": False}


def test_demo_seed_produces_a_full_funnel(store):
    result = demo.seed(store)
    assert result["total"] == 10 and result["positions"] == 11
    assert result["by_status"] == {
        "offer": 1, "interviewing": 1, "in_review": 6, "ghosted": 1, "rejected": 1}
    assert demo.is_seeded(store)
    # Watcher leads are in the pipeline but never in the funnel.
    con = db.connect()
    try:
        leads = con.execute("SELECT COUNT(*) FROM jobs WHERE status='new'").fetchone()[0]
    finally:
        con.close()
    assert leads == 5


def test_demo_seed_is_repeatable(store):
    first = demo.seed(store)
    assert demo.seed(store, reset=True) == first


def test_demo_refuses_a_directory_the_app_is_not_pointed_at(store, tmp_path):
    with pytest.raises(RuntimeError, match="different data directory"):
        demo.seed(tmp_path / "elsewhere")


def test_demo_refuses_to_write_over_real_data(store):
    (store / "master_profile.json").write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="not created by the demo"):
        demo.seed(store)


def test_doctor_names_what_is_missing_on_a_fresh_install(store, monkeypatch, capsys):
    from job_bot.__main__ import main

    _unconfigured(monkeypatch)
    assert main(["doctor"]) == 1          # no profile yet
    out = capsys.readouterr().out
    assert "[!!] Profile" in out and "python -m job_bot.build_profile" in out
    assert "local mode" in out
    assert "python -m job_bot demo" in out


def test_doctor_passes_once_a_profile_exists(store, monkeypatch, capsys):
    from job_bot.__main__ import main

    demo.seed(store)
    assert main(["doctor"]) == 0
    assert "Ready." in capsys.readouterr().out
