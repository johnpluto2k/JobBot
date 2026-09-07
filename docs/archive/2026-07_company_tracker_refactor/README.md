# July 2026 — company-first tracker refactor (archived hand-off documents)

These files were written at the repo root on 2026-07-09/10 when the internal
auto-recommend engine was retired in favour of the company tracker and manual
intake. They are the session artifacts of that work, kept for the record.
The current behaviour is described in `README.md` and `docs/CHANGELOG.md`.

- `company_tracker_prompt.md` — the prompt that specified the refactor.
- `IMPLEMENTATION_PLAN.md` — the phased plan with funnel-invariance checkpoints.
- `HANDOFF.md`, `QUICKSTART_HANDOFF.txt` — what was built and how to verify it.
- `REFACTOR_COMPLETE.md`, `refactor_summary.txt` — completion notes; the
  funnel counts quoted are historical.
- `UI_TEST_REPORT.md` — the Playwright run against the Companies page.

Two facts in these documents were later corrected: intake originally wrote the
portal name to `jobs.site`, which hid manual logs from the funnel until
2026-09-02, and re-logging a URL raised `IntegrityError` until the same fix.
