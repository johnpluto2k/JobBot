"""Google OAuth for the local FastAPI app (single-user).

Implements the authorization-code flow by hand (plain ``requests`` against
Google's OAuth endpoints — no oauthlib scope-normalization headaches) and owns
the two pieces of local persistence:

* ``data/google_token.json`` — the authorized-user record (refresh token +
  client id/secret) in the standard ``google.oauth2.credentials`` JSON shape,
  so ``gmail_client`` can load it with ``Credentials.from_authorized_user_*``.
* ``data/app_session.json`` — the opaque session token the dashboard cookie
  must match. One token = one logged-in browser session; logout deletes it.

Both files live under ``data/`` which is gitignored. This is deliberately a
local, single-user design — there is no user table, and "logged in" means
"this browser presented the cookie minted by the last successful Google login
on this machine".
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import time
from urllib.parse import urlencode

import requests

from . import config

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback"
).strip()

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"

# Full-URL forms — Google echoes these back, and gmail_client passes them to
# google-auth, which compares them verbatim on refresh.
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.readonly",
]

TOKEN_PATH = config.OUTPUT_DIR / "google_token.json"
SESSION_PATH = config.OUTPUT_DIR / "app_session.json"
SESSION_COOKIE = "jobbot_session"
SESSION_MAX_AGE = 30 * 24 * 3600  # seconds; matches the cookie's max_age

# In-flight OAuth states → (expiry, post-login redirect target). Single user,
# so a module dict is enough; entries die after 10 minutes.
_pending_states: dict[str, tuple[float, str]] = {}


def configured() -> bool:
    """True when the Google client credentials are present in the env."""
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


# --- Authorization-code flow ---------------------------------------------------

def build_auth_url(next_url: str = "/") -> str:
    """The Google consent URL for /auth/login to redirect to.

    ``access_type=offline`` + ``prompt=consent`` force a refresh token on every
    login (Google only issues one on first consent otherwise, and this app
    re-logs-in rarely enough that the extra consent screen is the right trade).
    """
    state = secrets.token_urlsafe(24)
    now = time.time()
    # Drop expired states while we're here.
    for k in [k for k, (exp, _) in _pending_states.items() if exp < now]:
        del _pending_states[k]
    _pending_states[state] = (now + 600, next_url)
    return AUTH_ENDPOINT + "?" + urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    })


def pop_state(state: str) -> str | None:
    """Validate a callback's state; returns the stashed next-URL or None."""
    entry = _pending_states.pop(state, None)
    if entry is None or entry[0] < time.time():
        return None
    return entry[1]


def _decode_jwt_claims(id_token: str) -> dict:
    """Claims from an ID token *without* signature verification — fine here
    because we received it directly from Google's token endpoint over TLS."""
    try:
        payload = id_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


def exchange_code(code: str) -> dict:
    """Trade the authorization code for tokens; persist the refresh token.

    Returns the identity claims ({"email": ..., "name": ...}) for the session.
    Raises ``RuntimeError`` with Google's error text on failure.
    """
    resp = requests.post(TOKEN_ENDPOINT, data={
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"token exchange failed ({resp.status_code}): {resp.text[:300]}")
    tok = resp.json()
    claims = _decode_jwt_claims(tok.get("id_token", ""))

    # Keep the previous refresh token if Google didn't send a fresh one
    # (shouldn't happen with prompt=consent, but don't lose auth if it does).
    refresh = tok.get("refresh_token")
    if not refresh and TOKEN_PATH.exists():
        try:
            refresh = json.loads(TOKEN_PATH.read_text(encoding="utf-8")).get("refresh_token")
        except Exception:
            refresh = None

    record = {
        # google.oauth2.credentials.Credentials.from_authorized_user_info shape
        "type": "authorized_user",
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh,
        "token": tok.get("access_token"),
        "scopes": (tok.get("scope") or " ".join(SCOPES)).split(),
        # our extras (ignored by google-auth):
        "email": claims.get("email"),
        "obtained_at": time.time(),
    }
    config.ensure_dirs()
    TOKEN_PATH.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return claims


def token_record() -> dict | None:
    """The stored authorized-user record, or None when never logged in."""
    if not TOKEN_PATH.exists():
        return None
    try:
        rec = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
        return rec if rec.get("refresh_token") else None
    except Exception:
        return None


def google_email() -> str | None:
    rec = token_record()
    return rec.get("email") if rec else None


# --- Dashboard session cookie ---------------------------------------------------

def create_session(email: str | None) -> str:
    """Mint the (single) session token and persist it; returns the cookie value."""
    token = secrets.token_urlsafe(32)
    config.ensure_dirs()
    SESSION_PATH.write_text(json.dumps({
        "token": token,
        "email": email,
        "created_at": time.time(),
    }), encoding="utf-8")
    return token


def session_valid(cookie_value: str | None) -> bool:
    if not cookie_value or not SESSION_PATH.exists():
        return False
    try:
        sess = json.loads(SESSION_PATH.read_text(encoding="utf-8"))
    except Exception:
        return False
    if time.time() - sess.get("created_at", 0) > SESSION_MAX_AGE:
        return False
    return secrets.compare_digest(str(sess.get("token")), cookie_value)


def destroy_session() -> None:
    SESSION_PATH.unlink(missing_ok=True)


def logout(revoke: bool = False) -> None:
    """Drop the session; optionally also revoke + delete the Google token."""
    destroy_session()
    if revoke:
        rec = token_record()
        if rec and rec.get("refresh_token"):
            try:
                requests.post("https://oauth2.googleapis.com/revoke",
                              params={"token": rec["refresh_token"]}, timeout=10)
            except Exception:
                pass
        TOKEN_PATH.unlink(missing_ok=True)
