"""Offline coaching regressions: stale sources, false urgency, memory, and read-only access."""
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

import pytest

from job_bot import applications, coach, config, db, growth
from job_bot.coach_context import build_snapshot

NOW = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "DATA_HOME", tmp_path)
    monkeypatch.setattr(config, "PROFILE_JSON", tmp_path / "master_profile.json")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "job_bot.db")
    config.PROFILE_JSON.write_text(json.dumps({"personal": {}, "targets": {}}), encoding="utf-8")
    with closing(db.connect()) as con:
        con.commit()
    (tmp_path / "gmail_sync_status.json").write_text(json.dumps({
        "last_sync": "2026-09-07T11:50:00+00:00", "last_error": None,
    }), encoding="utf-8")
    return tmp_path


def test_snapshot_never_initializes_or_migrates(store, monkeypatch):
    def no_writes():
        raise AssertionError("Snapshot opened a writable connection")

    monkeypatch.setattr(db, "connect", no_writes)
    monkeypatch.setattr(applications, "connect", no_writes)
    monkeypatch.setattr(growth, "build_applications", no_writes)
    before = db.DB_PATH.read_bytes()
    snapshot = build_snapshot(NOW)
    assert snapshot["funnel"]["total"] == 0
    assert snapshot["growth_focus_fields"] == []
    assert not [key for key in snapshot if key.endswith("_error")]
    assert db.DB_PATH.read_bytes() == before
    with closing(db.connect_readonly()) as con:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            con.execute("DELETE FROM jobs")


def test_missing_database_is_unavailable_not_empty(store):
    db.DB_PATH.unlink()
    snapshot = build_snapshot(NOW)
    assert "funnel" not in snapshot
    assert "funnel_error" in snapshot
    assert "db_error" in snapshot
    assert "growth_error" in snapshot
    assert not db.DB_PATH.exists()


@pytest.mark.parametrize("status,state", [
    ({"last_sync": "2026-09-07T11:50:00+00:00"}, "fresh"),
    ({"last_sync": "2026-09-01T12:00:00+00:00"}, "stale"),
    ({"last_sync": "2026-09-01", "last_error": "invalid_grant: revoked"}, "error"),
    ({"last_sync": "2026-09-08"}, "unknown"),
    ({"last_sync": "invalid"}, "unknown"),
    ([], "unknown"),
])
def test_sync_freshness_survives_stale_invalid_and_failed_sync(store, status, state):
    (store / "gmail_sync_status.json").write_text(json.dumps(status), encoding="utf-8")
    snapshot = build_snapshot(NOW)
    assert snapshot["freshness"]["state"] == state
    assert bool(snapshot["warnings"]) == (state != "fresh")


def test_past_and_unscheduled_interviews_are_not_upcoming(store):
    with closing(db.connect()) as con:
        con.executemany("INSERT INTO interviews (company, scheduled_at, status) VALUES (?,?,?)", [
            ("Past", "2026-09-06T12:00:00Z", "scheduled"),
            ("Unknown", None, "scheduled"),
            ("Future", "2026-09-07T09:00:00-04:00", "prepped"),
            ("Done", "2026-09-09T12:00:00Z", "done"),
        ])
        con.commit()
    snapshot = build_snapshot(NOW)
    assert [row["company"] for row in snapshot["upcoming_interviews"]] == ["Future"]
    assert {row["company"] for row in snapshot["interviews_needing_update"]} == {"Past", "Unknown"}


def test_acknowledgements_do_not_hide_actionable_automated_mail(store):
    with closing(db.connect()) as con:
        con.executemany(
            "INSERT INTO tracked_emails (received_at,sender,subject,company,category) VALUES (?,?,?,?,?)", [
                ("2026-09-07", "Careers <noreply@example.com>", "Thank you for your interest", "Ack", "recruiter_reply"),
                ("2026-09-07", "noreply@example.com", "Complete assessment", "Assessment", "assessment"),
                ("2026-09-07", "no-reply@example.com", "Interview invitation", "Interview", "interview_invite"),
                ("2026-09-07", "human@example.com", "Thank you for your interest", "Human", "recruiter_reply"),
                ("2026-05-07", "human@example.com", "Recruiter introduction", "Older", "recruiter_reply"),
            ],
        )
        con.commit()
    snapshot = build_snapshot(NOW)
    assert {row["company"] for row in snapshot["unhandled_recruiter_email"]} == {"Assessment", "Interview", "Human"}
    assert [row["company"] for row in snapshot["automated_acknowledgements"]] == ["Ack"]
    assert [row["company"] for row in snapshot["older_unhandled_email"]] == ["Older"]
    assert snapshot["email_counts"]["older_unhandled_email"] == 1
    with closing(db.connect_readonly()) as con:
        assert con.execute("SELECT SUM(handled) FROM tracked_emails").fetchone()[0] == 0


def test_new_ingestion_does_not_make_an_old_posting_fresh(store):
    with closing(db.connect()) as con:
        con.executemany("INSERT INTO jobs (title,status,priority,created_at,date_posted) VALUES (?,?,?,?,?)", [
            ("Old high score", "new", 99, "2026-07-01", "2026-07-01"),
            ("Reimported old", "new", 100, "2026-09-07", "2026-07-01"),
            ("Recent", "new", 70, "2026-09-06", "2026-09-05"),
            ("No posting date", "new", 60, "2026-09-06", None),
        ])
        con.commit()
    assert [row["title"] for row in build_snapshot(NOW)["fresh_high_priority_jobs"]] == ["Recent", "No posting date"]


def test_missing_optional_table_does_not_hide_other_sections(store):
    with closing(db.connect()) as con:
        con.execute("DROP TABLE outreach")
        con.commit()
    snapshot = build_snapshot(NOW)
    assert "followups_due_error" in snapshot
    assert snapshot["upcoming_interviews"] == []
    assert snapshot["fresh_high_priority_jobs"] == []


def test_coach_reads_primary_memory_and_keeps_freshness_caveats(store, monkeypatch):
    (store / "COACH.md").write_text("Balanced coaching brief", encoding="utf-8")
    (store / "COACH_STATE.md").write_text("Keep the agreed employer tracks separate.", encoding="utf-8")
    linked = store / "linked-checkout"
    linked.mkdir()
    (linked / "COACH_STATE.md").write_text("OUTDATED WORKTREE MEMORY", encoding="utf-8")
    monkeypatch.setattr(config, "PROJECT_ROOT", linked)
    prompt = coach.coach_system({"freshness": {"state": "error"}})
    assert "Keep the agreed employer tracks separate." in prompt
    assert "OUTDATED WORKTREE MEMORY" not in prompt
    assert "never infer inactivity from missing mail" in prompt
    assert '"state": "error"' in prompt


def test_cli_uses_dashboard_snapshot_builder(store, monkeypatch, capsys):
    import coach_snapshot
    monkeypatch.setattr(coach, "build_snapshot", lambda: {"shared": "snapshot"})
    monkeypatch.setattr("sys.argv", ["coach_snapshot.py"])
    coach_snapshot.main()
    assert json.loads(capsys.readouterr().out) == {"shared": "snapshot"}
