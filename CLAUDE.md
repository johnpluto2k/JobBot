# Job Bot — project context for Claude Code

This repo is John Bae's personal job-search automation system (résumé tailoring,
ATS scoring, application tracking, growth planning — see `README.md` and
`job_application_system_master_plan.md` for the full architecture). It also
doubles as the entry point for **career coaching** — a separate Claude Code
session opened in this folder should be able to act as John's job-search coach
on request, without any extra setup.

This file is auto-loaded by Claude Code at the start of every session here, so
read it before doing anything else in this repo.

## Two modes

**1. Engineering on the codebase** (the default when John asks for a code
change, bug fix, new feature, etc.) — work normally as a coding assistant. The
`job_bot/` package, `data/job_bot.db` (SQLite), and `data/master_profile.json`
are the core pieces; `README.md` explains the phases.

**2. Coaching mode** — trigger this whenever John asks something like "how am
I doing", "what should I focus on today", "am I on track", "should I keep
waiting on [company]", or otherwise wants a read on his job search rather than
a code change. When that happens:

1. Read `COACH.md` at the repo root first — it defines the coaching tone
   (**note:** `COACH.md` is intentionally gitignored and local-only, since it
   contains personal job-search context. If you cloned this repo and the file
   isn't present, coaching mode simply isn't configured — skip to step 2.)
   (**balanced**: real, specific praise for real wins; direct/candid about
   stalling or avoidance; always ends in a concrete next action) and the exact
   data sources.
2. Read `COACH_STATE.md` next — it is the **running memory of the coaching
   conversation** so you can pick up mid-thread instead of making John restart.
   It holds decisions already made (don't relitigate them), corrections to
   things previously gotten wrong (don't repeat them), open threads, and a
   dated log. It deliberately contains **no live metrics** — those come from
   the snapshot in step 3, which is always current.
   (Also gitignored and local-only; if it isn't present, skip it.)

   **At the end of any substantive coaching session, update it**: refresh
   "Open threads" and "Next actions", and append a dated line to the Log.
   That upkeep is what makes the next session continuous. Keep it under
   ~150 lines — compress old log entries rather than letting it sprawl.

3. Pull a live snapshot before saying anything specific:
   ```bash
   python3 coach_snapshot.py .
   ```
   This prints JSON with the canonical application funnel
   (`job_bot.applications.summary()` — offer/rejected/ghosted/interviewing/
   in_review counts, response rate, interview rate; this is the one source of
   truth, don't recompute from the raw `jobs` table, which has duplicates),
   upcoming interviews, overdue follow-ups, unhandled recruiter email, fresh
   high-priority unactioned postings, and the growth plan's insights/focus
   fields. It's read-only — it never writes to the DB or any file. Since this
   runs in John's actual dev environment (not a sandbox), all of job_bot's
   real dependencies should already be installed per `requirements.txt`, so
   the growth-plan part should work too — if it errors on a missing package,
   just tell John which `pip install` would fix it.
4. Coach, don't report: answer what John actually asked using the 1-2 facts
   from the snapshot that matter, not a dump of every number. Lead with
   anything time-sensitive (an interview coming up, an overdue follow-up,
   unhandled recruiter email that might be a live opportunity), give one
   honest observation grounded in the real data, and close with exactly one
   concrete action. Never fabricate a number, company detail, or "you're
   doing great" the data doesn't support — the coaching is only valuable
   because it's trustworthy, not because it's nice.

## Why this works as "a separate chat that still talks to this setup"

Any `claude` session started in this folder — on this machine, independent of
any other chat — reads this file automatically, so it has the same grounding
and persona without needing anything scheduled or pre-connected. Just open a
terminal in this folder, run `claude`, and ask a coaching question.

## Manual job intake (company-first workflow)

As of 2026-07-09, the **manual intake flow** is the primary way to log jobs:

**When John finds a job and applies**, the fastest path is the **Log a job**
button on the Companies page of the dashboard (`LogJobForm`). Point him there
rather than at the CLI unless he asks for it.

Equivalently, from a terminal:

1. Get the posting URL, company name, and job title
2. Run (or submit via the API):
   ```bash
   python -m job_bot.intake "<url>" "<company>" "<title>" [--portal linkedin] [--status applied]
   ```
   Portals: indeed, linkedin, jobright, glassdoor, ziprecruiter, workday, greenhouse, handshake, smith, email, other (default)
   Statuses: applied, saved, rejected, offer (default: applied)

3. The job appears in the company tracker and applications funnel immediately

Two things to know before touching this path (both fixed 2026-09-02, don't
reintroduce them):

- Intake writes **`site='tracker'`**, not the portal name.
  `applications.build_applications()` reads only
  `WHERE site IN ('email','tracker','ledger')`, so writing the portal made every
  manually logged job invisible to the funnel. The portal lives on the company
  row and in the job's notes.
- **Re-logging the same URL updates that row.** `jobs.url` is UNIQUE, so a bare
  INSERT raised `IntegrityError` behind an opaque 500.

**If integrating with a form/UI:**

POST to `/api/intake`:
```json
{
  "url": "https://...",
  "company": "KPMG",
  "title": "Senior Auditor",
  "portal": "linkedin",
  "status": "applied"
}
```

**The company tracker:**

List all companies or only those overdue for a check:
```bash
# CLI (via Python):
from job_bot import companies
companies.list_all()              # all companies
companies.due_for_check()         # overdue for check

# API:
GET /api/companies
GET /api/companies?due_for_check=true
```

Mark a company as checked today (reschedule next check for 7 days out):
```bash
PATCH /api/companies/{id} { "next_check_in_days": 7 }
```

## Company posting watcher (2026-09-02)

`job_bot/watch.py` polls tracked companies for **new** openings so the pipeline
fills itself. 88 of 203 companies have a verified public job-board endpoint,
curated in `job_bot/watch_registry.py` (Greenhouse, Ashby, SmartRecruiters,
Workday). Runs every 6 hours from the same APScheduler that drives the Gmail
sync; `companies.next_check_due` is the work queue.

```bash
python -m job_bot.watch --dry-run    # what a pass would find, saving nothing
python -m job_bot.watch              # poll everything currently due
```
```
GET  /api/watch/status               # who's watched + last-pass results
POST /api/watch/run                  # poll now
```

When working on it:

- **Don't add companies by guessing ATS tokens.** Guessing produces confident
  garbage — `costar` is an astrology app, `diligent` is a construction firm, and
  SmartRecruiters returns HTTP 200 with `totalFound: 0` for tokens that don't
  exist. Verify against the live endpoint and add to `watch_registry.py`.
- Deloitte, EY, KPMG and Protiviti have **no public feed** (Phenom People /
  Taleo / iCIMS / SuccessFactors). They stay on the manual check-in nudge.
- Watcher rows are written with `site='<platform>'` so they can never reach the
  applications funnel. Keep it that way — a posting John hasn't applied to is
  not an application.
- Email alerts are impossible: the OAuth scope is `gmail.readonly` and there is
  no send path. Reporting goes to console, `JOB_BOT_WEBHOOK`, the dashboard and
  the coach snapshot.

## One `data/` per repo, not per worktree

`data/` is gitignored, so it is **not** shared between git worktrees.
`config._primary_checkout()` resolves it to the primary checkout from any
worktree, which is why a profile edit made in one worktree is now visible to the
running app. Before that fix each worktree kept a private `job_bot.db` and
`master_profile.json`, and edits silently went nowhere. If something looks like
it "didn't save", check which `data/` was actually written.

## Browsing job boards

> **⚠️ 2026-08-25: `agent-browser` does not work on this machine.** It is installed
> but ships no arm64 Windows binary — `agent-browser --version` fails with
> `No binary found for win32-arm64`. Until an arm64 build exists, use the
> **Chrome MCP tools** instead: `mcp__claude-in-chrome__navigate` to the URL, then
> `mcp__claude-in-chrome__get_page_text` to read it. Plain `curl`/WebFetch is not a
> substitute for JS-rendered boards — `careers.google.com`, for one, returns an empty
> SPA shell with no listings in the HTML. The rest of this section is kept for when
> `agent-browser` works again.

## Browsing job boards: use `agent-browser`

For any pipeline step that needs to browse or scrape a job board (or any other
live web page), use the globally installed `agent-browser` CLI instead of raw
HTTP fetches or heavier browser MCP servers — it returns a compact
accessibility-tree snapshot instead of full HTML, so it is far cheaper in
tokens and handles JavaScript-rendered listings that plain fetches miss.

Typical loop:

```bash
agent-browser open https://www.linkedin.com/jobs/search?keywords=...
agent-browser snapshot            # lists interactive elements as @e1, @e2, ...
agent-browser click @e5           # e.g. open a posting
agent-browser fill @e3 "python developer"   # e.g. type into the search box
```

Re-run `snapshot` after each navigation/click to get fresh element refs. This
is a tooling note only — the pipeline stages, prompts, and outputs in
`daily_pipeline_prompt.md` are unchanged.
