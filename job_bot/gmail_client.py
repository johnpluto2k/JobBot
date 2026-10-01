"""Gmail fetcher: pulls recent job-related threads via the Gmail API and feeds
them to the existing ``gmail_sync`` transform.

Split into two layers so the interesting part stays offline-testable:

* **Transform boundary** (pure, no network): ``thread_to_record`` maps one raw
  Gmail API thread (``users.threads.get`` with ``format="full"``) to the
  thread shape ``gmail_sync.normalize_thread`` expects — headers flattened,
  text/plain bodies base64url-decoded, SENT label preserved so outbound
  messages are recognized.
* **I/O layer**: ``fetch_recent_threads`` (list + get against the API) and
  ``run_sync`` (fetch → ``gmail_sync.sync_threads`` → persist a status file
  the dashboard's sync indicator reads).

Auth comes from the refresh token ``google_auth`` stored at login; google-auth
refreshes the access token transparently.
"""

from __future__ import annotations

import base64
from html import unescape as _unescape
import json
import os
import re
import threading
import time
from datetime import datetime, timezone

from . import config, google_auth

# Recruiting-flavored Gmail query. Deliberately broad — gmail_sync's noise
# filter + drop_other do the real filtering — but keyword-scoped so a sync
# doesn't page through the whole inbox every 15 minutes.
DEFAULT_QUERY = (
    "-in:chat -in:spam -in:trash "
    "(interview OR application OR recruiter OR offer OR assessment OR "
    'applying OR candidacy OR hirevue OR "talent acquisition" OR '
    '"phone screen" OR "moving forward" OR position)'
)
SYNC_QUERY = os.getenv("GMAIL_SYNC_QUERY", DEFAULT_QUERY)
SYNC_DAYS = int(os.getenv("GMAIL_SYNC_DAYS", "7"))
SYNC_MAX_THREADS = int(os.getenv("GMAIL_SYNC_MAX_THREADS", "100"))

STATUS_PATH = config.OUTPUT_DIR / "gmail_sync_status.json"

# One sync at a time: the 15-minute job and POST /api/sync-now share this.
_sync_lock = threading.Lock()


# --- Transform boundary (pure — tested offline in tests/test_gmail_client.py) --

def _b64url_decode(data: str) -> str:
    try:
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode(
            "utf-8", errors="replace")
    except Exception:
        return ""


def _headers(payload: dict) -> dict[str, str]:
    """Flatten payload headers to a lowercase-keyed dict (first value wins)."""
    out: dict[str, str] = {}
    for h in payload.get("headers") or []:
        name = str(h.get("name", "")).lower()
        if name and name not in out:
            out[name] = str(h.get("value", ""))
    return out


def _strip_html(html: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = _unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _plain_body(payload: dict) -> str:
    """Best text body in the MIME tree: prefer text/plain, fall back to
    stripped text/html. Walks nested multipart/* parts depth-first."""
    plain: list[str] = []
    html: list[str] = []

    def walk(part: dict) -> None:
        mime = part.get("mimeType", "")
        data = (part.get("body") or {}).get("data")
        if data:
            if mime == "text/plain":
                plain.append(_b64url_decode(data))
            elif mime == "text/html":
                html.append(_b64url_decode(data))
        for sub in part.get("parts") or []:
            walk(sub)

    walk(payload)
    if plain:
        return "\n".join(plain).strip()
    if html:
        return _strip_html("\n".join(html))
    return ""


def message_to_record(msg: dict) -> dict:
    """One Gmail API message → the flat shape gmail_sync reads per message."""
    payload = msg.get("payload") or {}
    h = _headers(payload)
    return {
        "id": msg.get("id", ""),
        "from": h.get("from", ""),
        "subject": h.get("subject", ""),
        "date": h.get("date", ""),
        "plaintextBody": _plain_body(payload),
        "snippet": msg.get("snippet", ""),
        "labelIds": msg.get("labelIds") or [],
        "toRecipients": [h["to"]] if h.get("to") else [],
        "ccRecipients": [h["cc"]] if h.get("cc") else [],
    }


def thread_to_record(thread: dict) -> dict:
    """One Gmail API thread → the record gmail_sync.normalize_thread expects."""
    msgs = [message_to_record(m) for m in thread.get("messages") or []]
    first = msgs[0] if msgs else {}
    return {
        "id": thread.get("id", ""),
        "subject": first.get("subject", ""),
        "snippet": thread.get("snippet") or first.get("snippet", ""),
        "messages": msgs,
    }


# --- Gmail API I/O ---------------------------------------------------------------

def _credentials():
    from google.oauth2.credentials import Credentials

    rec = google_auth.token_record()
    if not rec:
        raise RuntimeError("not logged in — no Google refresh token stored")
    return Credentials.from_authorized_user_info(rec)


def _service():
    from googleapiclient.discovery import build

    # cache_discovery=False: the file cache needs oauth2client and just warns.
    return build("gmail", "v1", credentials=_credentials(), cache_discovery=False)


def fetch_recent_threads(days: int = SYNC_DAYS,
                         max_threads: int = SYNC_MAX_THREADS,
                         query: str = SYNC_QUERY) -> list[dict]:
    """Recent job-related threads, already mapped for gmail_sync."""
    svc = _service()
    q = f"newer_than:{days}d {query}".strip()
    refs: list[dict] = []
    page_token = None
    while len(refs) < max_threads:
        resp = svc.users().threads().list(
            userId="me", q=q, maxResults=min(max_threads - len(refs), 100),
            pageToken=page_token,
        ).execute()
        refs.extend(resp.get("threads") or [])
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    out = []
    for ref in refs[:max_threads]:
        raw = _with_backoff(svc.users().threads().get(
            userId="me", id=ref["id"], format="full"))
        out.append(thread_to_record(raw))
    return out


def _with_backoff(request, attempts: int = 5):
    """Execute a Gmail request, waiting out per-minute quota errors.

    A backfill of a few hundred threads trips "Units per minute per user"
    (HTTP 403/429 rateLimitExceeded) partway through; the quota refills within
    a minute, so wait and retry rather than failing the whole pass.
    """
    from googleapiclient.errors import HttpError

    for i in range(attempts):
        try:
            return request.execute()
        except (ConnectionError, TimeoutError):
            # A long backfill also sees the odd reset connection (WinError 10054).
            if i == attempts - 1:
                raise
            time.sleep(2 * (i + 1))
        except HttpError as exc:
            status = getattr(exc.resp, "status", 0)
            if status not in (403, 429) or "rate" not in str(exc).lower() or i == attempts - 1:
                raise
            time.sleep(min(60, 5 * 2 ** i))


# --- Sync orchestration + status -------------------------------------------------

def load_status() -> dict:
    if not STATUS_PATH.exists():
        return {"last_sync": None, "last_result": None, "last_error": None}
    try:
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"last_sync": None, "last_result": None, "last_error": None}


def _write_status(status: dict) -> None:
    config.ensure_dirs()
    STATUS_PATH.write_text(json.dumps(status, indent=2), encoding="utf-8")


def sync_running() -> bool:
    return _sync_lock.locked()


def run_sync(days: int = SYNC_DAYS, max_threads: int = SYNC_MAX_THREADS) -> dict:
    """Fetch → classify/dedupe/persist (gmail_sync) → record status.

    Returns the status dict. Never raises: an error lands in ``last_error`` so
    the scheduler survives and the dashboard can surface it. If a sync is
    already in flight, returns the current status untouched.
    """
    from .gmail_sync import sync_threads

    if not _sync_lock.acquire(blocking=False):
        return load_status()
    try:
        try:
            threads = fetch_recent_threads(days=days, max_threads=max_threads)
            summary = sync_threads(threads)
            status = {
                "last_sync": datetime.now(timezone.utc).isoformat(),
                "last_result": {k: summary[k] for k in
                                ("scanned", "new", "skipped", "noise", "dropped",
                                 "by_category")},
                "last_error": None,
            }
        except Exception as exc:
            status = load_status()
            status["last_error"] = f"{type(exc).__name__}: {exc}"
            status["last_error_at"] = datetime.now(timezone.utc).isoformat()
        _write_status(status)
        return status
    finally:
        _sync_lock.release()


def resync(days: int = 60, max_threads: int = 400) -> dict:
    """Re-read recent threads and rebuild their tracker rows with the current
    classifier.

    A normal sync skips any thread it has seen, so a fix to classification or
    company detection never reached rows already stored: IBM's assessment
    stayed a rejection, three Mastercard receipts stayed one row with no
    company. This replaces the rows for every fetched thread, keeps each row's
    `handled` flag, and removes the auto-logged rejection a misread email
    created (rejections with source='inbox' for that company and date).
    """
    from .db import connect
    from .gmail_sync import sync_threads

    with _sync_lock:
        threads = fetch_recent_threads(days=days, max_threads=max_threads)
        con = connect()
        try:
            handled: dict[str, int] = {}
            removed = 0
            for t in threads:
                tid = t.get("id")
                if not tid:
                    continue
                rows = con.execute(
                    "SELECT id, gmail_id, company, category, received_at, handled "
                    "FROM tracked_emails WHERE gmail_id = ? OR gmail_id LIKE ?",
                    (tid, f"{tid}:%")).fetchall()
                for r in rows:
                    handled[r["gmail_id"]] = r["handled"] or 0
                    if r["category"] == "rejection" and r["company"]:
                        victim = con.execute(
                            "SELECT id FROM rejections WHERE source='inbox' AND company=? "
                            "AND rejected_on=? LIMIT 1",
                            (r["company"], r["received_at"])).fetchone()
                        if victim:
                            con.execute("DELETE FROM rejections WHERE id=?", (victim["id"],))
                    con.execute("DELETE FROM tracked_emails WHERE id=?", (r["id"],))
                    removed += 1
            con.commit()
        finally:
            con.close()

        summary = sync_threads(threads)

        con = connect()
        try:
            for gid, flag in handled.items():
                if flag:
                    con.execute("UPDATE tracked_emails SET handled=? WHERE gmail_id=?", (flag, gid))
            con.commit()
        finally:
            con.close()
    summary["replaced"] = removed
    return summary


def run_sync_if_logged_in() -> None:
    """Scheduler entry point: no-op until the user has logged in once."""
    if google_auth.token_record():
        run_sync()


if __name__ == "__main__":  # manual one-shot: python -m job_bot.gmail_client
    # python -m job_bot.gmail_client --resync 60   → rebuild the last 60 days
    import sys

    from .gmail_sync import format_report, sync_threads

    t0 = time.time()
    if len(sys.argv) > 1 and sys.argv[1] == "--resync":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 60
        result = resync(days=n)
        print(format_report(result))
        print(f"replaced {result['replaced']} stored rows")
    else:
        threads = fetch_recent_threads()
        print(format_report(sync_threads(threads)))
    print(f"({time.time() - t0:.1f}s)")
