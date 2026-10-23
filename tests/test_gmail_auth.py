"""Gmail sync failures the dashboard must explain, not just log (2026-10-22).

Sync had been down since 2026-09-29: the stored login came back from Google's
consent screen without the Gmail scope, and the one before it had expired
(an OAuth app in Testing mode drops refresh tokens after 7 days).
"""

import json

import pytest

from job_bot import gmail_client, google_auth


@pytest.fixture
def token_file(tmp_path, monkeypatch):
    path = tmp_path / "google_token.json"
    monkeypatch.setattr(google_auth, "TOKEN_PATH", path)
    monkeypatch.setattr(gmail_client, "STATUS_PATH", tmp_path / "status.json")

    def write(scopes):
        path.write_text(json.dumps({
            "type": "authorized_user", "client_id": "id", "client_secret": "s",
            "refresh_token": "r", "token": "t", "scopes": scopes,
        }), encoding="utf-8")
    return write


def test_login_without_gmail_scope_is_reported_as_such(token_file):
    token_file(["openid", "https://www.googleapis.com/auth/userinfo.email"])
    assert not google_auth.gmail_granted()
    status = gmail_client.run_sync()
    assert status["last_error"] == google_auth.GMAIL_NOT_GRANTED
    assert "not granted" in status["last_error"]  # the dashboard's Reconnect trigger


def test_login_with_gmail_scope_is_granted(token_file):
    token_file(google_auth.SCOPES)
    assert google_auth.gmail_granted()


def test_expired_refresh_token_explains_testing_mode():
    from google.auth.exceptions import RefreshError

    exc = RefreshError("invalid_grant: Token has been expired or revoked.",
                       {"error": "invalid_grant"})
    msg = gmail_client.describe_error(exc)
    assert msg.startswith("invalid_grant")  # the dashboard's Reconnect trigger
    assert "Testing mode" in msg


def test_other_errors_pass_through():
    assert gmail_client.describe_error(TimeoutError("slow")) == "TimeoutError: slow"
