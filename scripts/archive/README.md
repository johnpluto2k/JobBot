# Archived one-off scripts

Kept for the record; not maintained and not collected by pytest
(`pytest.ini` scopes collection to `tests/`).

- `test_ui.py`, `test_ui_fixed.py` — Playwright end-to-end checks written for
  the July 2026 company-tracker refactor. They start the dev servers and click
  through the Companies page.
- `test_api_direct.py` — starts the API and prints `/api/companies` and
  `/api/summary`.
- `verify_system.py` — one-time verification that the tracker was wired and the
  funnel unchanged after the refactor. **It writes a test job to the live
  database**; don't run it casually.

The maintained tests live in `tests/`.
