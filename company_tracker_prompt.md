# Refactor: replace internal job search with a company tracker

## Context

This is Job Bot, a Python job-application pipeline for John Bae (UMD accounting student, targeting IT Audit / Tech Risk, FinTech Ops/Risk, Data Analytics / FP&A, Big 4 Audit — see `data/master_profile.json`). Code lives in `job_bot/`, SQLite DB at `data/job_bot.db`, React UI in `web/`.

The internal search/scoring engine is being retired: its priority scores surface irrelevant postings (top "matches" right now are Clinical Medical Physics professorships and a Police Aide role). The new model: **the bot tracks companies; John searches and applies manually** on LinkedIn, Indeed, Jobright, Glassdoor, ZipRecruiter, Workday portals, Handshake, and the UMD Smith School portal, then logs applications in the bot.

## Goal

Company-first tracking. The bot's job is remembering where to look and what happened — not deciding what's relevant.

## Tasks

### 1. New `companies` table + module

There is no companies table today — companies exist only as strings in `jobs.company`. Create:

```sql
companies (
  id, name, name_normalized (unique),
  career_site_url, ats_platform,        -- e.g. Workday, Greenhouse, iCIMS
  portals,                              -- JSON list: which of the sites above it posts on
  target_fields,                        -- JSON list: e.g. ["IT Audit", "Audit & Assurance"]
  tier,                                 -- Big4 / mid-tier / boutique / other
  notes, last_checked, next_check_due, created_at
)
```

Add `job_bot/companies.py` with CRUD + `due_for_check()` (companies where `next_check_due <= today`, default cadence 7 days).

### 2. Migration: seed from existing data

Write a migration script that seeds `companies` from distinct `jobs.company` values (~53 companies incl. Deloitte, KPMG, PwC, BDO, Grant Thornton). Reuse the existing name-normalization/dedup logic that `job_bot.applications.summary()` uses. Best-effort fill `career_site_url` and `ats_platform` from existing `jobs.url` / `jobs.site` values; leave blank where unknown rather than guessing.

### 3. Retire the search/scoring pipeline

- Deprecate (don't delete yet): `search_jobs.py`, `jobsearch.py`, `score_job.py`, `jobright.py`, and the scraping entry points in `pipeline.py`. Move to a `job_bot/deprecated/` package or gate behind a `--legacy-search` flag so nothing imports them by default.
- `scrape_log` table stays as-is (historical data).
- Keep `legitimacy.py` and `jd_parser.py` — still useful when John pastes a posting he found manually.

### 4. Manual intake flow

Add a fast path to log a job John found himself: CLI command (and API endpoint) taking URL + company + title + which portal he found it on. It should link to the `companies` row (creating one if new), skip all scoring, and set status directly (default `applied` since he's logging after applying, with option for `saved`).

### 5. UI: tracker view

In `web/`, replace the job-search/priority-feed view with a company tracker: table of companies with tier, portals, last checked, next check due, open applications count, and a one-click "checked today" button. Keep the existing funnel/applications views untouched.

## Constraints

- **Do not break `job_bot.applications.summary()`** — it is the canonical funnel used by the coaching skill and daily check-in. Run it before and after; output must be identical.
- All schema changes via migration script, idempotent, with a backup copy of `data/job_bot.db` taken first.
- Don't modify `COACH.md`, `daily_pipeline_prompt.md`, or the scheduled tasks.
- Add/update tests in `tests/` for the migration, `companies.py`, and the manual intake path.
- Update `README.md` and `CLAUDE.md` to reflect the new workflow.

## Verify

1. Migration runs clean on a copy of the real DB; company count matches the deduped funnel count.
2. `applications.summary()` unchanged before vs. after.
3. Manual intake round-trip: log a fake job → appears under its company → funnel counts update.
4. `python -m pytest tests/` passes.
