# Changelog

Dated history of the major passes. Newest first. Details for older entries
live in `docs/archive/` and the git log.

## 2026-09-07 — Coaching memory, shared snapshot, and a repo anyone can run

- **One read-only snapshot for every coach.** `job_bot/coach_context.py` now
  backs both `coach_snapshot.py` and the dashboard Coach tab. It opens SQLite in
  `mode=ro` with `query_only=ON`, never creates or migrates, and reports a
  missing database as an error rather than zero applications.
- **Freshness is first-class.** The snapshot carries a `freshness` block from
  `data/gmail_sync_status.json` (fresh / stale / error / unknown) and
  `warnings`; the Coach tab and header show the last successful sync and a
  **Reconnect Google** link on `invalid_grant`.
- **Less false urgency.** Unhandled recruiter mail is split into recent,
  older-than-30-days, and automated acknowledgements. Past or unscheduled
  interviews are listed as needing an update, not as upcoming. "Fresh" postings
  must be both recently ingested and recently posted.
- **`COACH_STATE.md` is read by every entry point.** The dashboard coach's
  system prompt includes the running memory and explicit caveats; the CLI
  coach delivers the START HERE briefing and updates the file after substantive
  sessions. `docs/codex_coaching.md` documents the separation between the
  coach and engineering sessions. Nine regression tests in
  `tests/test_coach_context.py`.
- **No person is hardcoded.** New `job_bot/candidate.py` derives name, school,
  major, graduation date, and target roles from the profile (with env
  fallbacks). Cover letters, thank-you notes, LinkedIn drafts, outreach pitches
  and affiliation phrases, mock-interview personas, the company brief, the
  role summary, and the coach system prompt all use it. The watcher's home
  region is `JOB_BOT_HOME_MARKERS`. Launcher scripts find the repo from their
  own path.
- **Docs rewritten around the process.** `README.md` explains the six-step
  loop and the coach; `docs/SETUP.md` and `docs/SETUP_PROMPT.md` onboard a new
  owner (including Overleaf and Claude in Chrome); `docs/PERSONALIZATION.md`
  lists what is still field-specific; `templates/` holds starting points for
  the private coaching files. July's hand-off documents moved to
  `docs/archive/2026-07_company_tracker_refactor/`; one-off root scripts moved
  to `scripts/archive/`; `pytest.ini` scopes collection to `tests/`.
- `scripts/seed_broad_targets.py` (multi-lane target list) committed.

## 2026-09-02 — Correctness pass and the company posting watcher

- Promotional email was being filed as job offers (seven "offers", all
  marketing blasts). Added a noise rule, tightened the offer signal, fixed
  `detect_company()` matching short aliases anywhere in a body, and replaced an
  unbounded `UPDATE … LIKE '%company%'` with id-scoped updates capped at ten
  rows. `scripts/repair_inbox_misclassification.py` repairs existing data.
- Newsletters and event RSVPs no longer enter the funnel; a re-application can
  outlive an old rejection.
- `companies.match_key()` normalizes entity suffixes without merging distinct
  organizations.
- Manual intake writes `site='tracker'` (it had been invisible to the funnel),
  re-logging a URL updates instead of 500ing, and the Companies page gained
  **Log a job**.
- `data/` is resolved to the primary checkout from any git worktree.
- `deprecated/jobsearch.py` was unimportable, which had silently taken down
  Find Jobs; fixed.
- New `job_bot/watch.py` + `watch_registry.py`: 88 of 203 companies polled
  every 6 hours across Greenhouse, Ashby, SmartRecruiters, and Workday, with a
  word-boundary location filter. `notify.py` wired to watcher results. SQLite
  moved to WAL with a 30 s busy timeout.
- Dashboard: one failed request no longer blanks every page; long tables are
  searchable and sortable; TypeScript `strict` on. Tests 30 → 60.
- Launcher (`start-job-bot.cmd`) tracks Orca tabs by handle and fast-forwards
  the checkout without ever moving backward.

## 2026-08-31 — Résumé generator audit

- Found that `generated_resumes` is write-only with no outcome linkage, an
  ATS-score regression between renders, and a JD field-swap bug. Established
  the bullets-first workflow (ship tailored bullets; the owner formats in
  Overleaf) and that the contract's ATS ≥ 85 gate is unreachable with TF-IDF
  similarity.

## 2026-08-25 — Repo made public

- `COACH.md` purged from history; coaching files, documents, inputs, and résumé
  folders confirmed gitignored. Noted that the `agent-browser` CLI has no
  win32-arm64 binary; Claude in Chrome tools are used instead.

## 2026-07-22 — Four branches reconciled into `main`

- Google sign-in + autonomous Gmail sync (07-13), the company-first tracker
  refactor + Tech v4 résumé (07-09/10), and the sidebar-nav frontend redesign
  (07-16) had been built independently. Merged, with a company-name dedup bug
  and the unwired `qualifications.py` recorded as follow-ups.

## 2026-07-16 — React dashboard redesign

- Grouped sidebar replaces the tab strip, drawer below `md`, Resume Studio
  mounted under Build, Find Jobs site picker and results slider, unified error
  panel.

## 2026-07-13 — Google sign-in and autonomous Gmail sync

- Hand-rolled OAuth code flow (`openid email profile gmail.readonly`), single-
  user session cookie, `/api/*` gated. Gmail threads pulled every 15 minutes
  through the existing classification pipeline; sync indicator in the header.

## 2026-07-09/10 — Company-first tracker

- Retired the internal auto-recommend engine (it surfaced Clinical Medical
  Physics professorships as top matches). Added the `companies` table,
  `companies.py`, `intake.py`, `/api/intake`, `/api/companies`, the Companies
  page, and a one-time migration seeding 53 companies from history.
  `applications.summary()` verified identical before and after. Hand-off
  documents in `docs/archive/2026-07_company_tracker_refactor/`.

## 2026-07-07 — Résumé template by field

- Tech fields render through RenderCV/Typst (`engineeringresumes` theme);
  business fields through the DOCX renderer.

## 2026-07-05 — Writing quality and Resume Studio

- Anti-cliché style rules (`writing_style.py`) applied to bullets, letters,
  LinkedIn About, and the coach. Streamlit Resume Studio (YAML editor → PDF).

## 2026-07-02 — Tune-ups

- Safer scraping defaults (Indeed only, per-site delays, 429 backoff, scrape
  log), cheaper LLM calls (fast model for mechanical rewrites, prompt-cached
  profile block, right-sized `max_tokens`), and the RenderCV résumé pipeline
  with a one-page regression test across all renderers.

## Before July 2026

- Phases 1–9 of `docs/job_application_system_master_plan.md`: profile
  extraction, reverse ATS scoring, the network-vs-cold-apply decision engine,
  tailored generation, search and routing, networking and outreach, interview
  prep, assisted autofill, the Streamlit control center, plus the tracking and
  communications layer (inbox triage, prep plans, thank-yous, salary and offer
  tools, LinkedIn optimizer, cover-letter A/B, notifications, recording
  analysis, rejection analytics, network map).
