# Agentic Job Application System

Personal AI-powered career platform. Full roadmap lives in
[`docs/job_application_system_master_plan.md`](docs/job_application_system_master_plan.md).

**Status: ALL 9 PHASES + ALL 15 RECOMMENDATIONS + CAREER-OPS LAYER + TUNE-UPS COMPLETE ✅**
(~60 modules, incl. the three tune-up workstreams from
[`docs/prompts/tuneups_adjustments.md`](docs/prompts/tuneups_adjustments.md):
safer scraping, prompt-cached/right-sized LLM calls, RenderCV resume pipeline.)
Knowledge base · reverse ATS scorer · network-vs-cold-apply · tailored
resume/cover-letter generator · job search + routing · networking/outreach ·
interview prep + mock · application autofill · 13-tab Streamlit control center
(incl. an **Applications tracker** — one deduped, field-classified row per
position applied — and an automated **Growth Plan** of certs/projects/résumé
variants).
Plus the recommendations layer: application tracking, inbox triage, calendar
prep, thank-you drafts, salary intelligence, LinkedIn optimizer, referral packs,
company research briefs, rejection + cover-letter A/B analytics, fresh-job
notifications, interview-recording analysis, offer comparison, and an alumni
network map.

**Two front ends, same data.** The original 13-tab **Streamlit** dashboard
(now incl. **Resume Studio** — edit the RenderCV YAML as text, typeset to a
Typst PDF, download the `.typ`/`.yaml`/`.pdf`)
(`streamlit run job_bot/dashboard.py`, port 8501) is still here, but the primary
UI is now a modern **React dashboard** (`web/`, Vite + Tailwind + shadcn-style
components) served by a thin **FastAPI** layer (`job_bot/api.py`) that reuses the
exact same Python logic — so every number matches. In single-server mode one
`uvicorn` process serves both the UI and the API on **port 8000**. It adds an
LLM **Career Coach** chat grounded in your live pipeline. See
[Phase 9 — the dashboard](#phase-9--the-dashboard-control-center--front-end).

Phase 1 reads every resume / cover letter / project doc, extracts a structured
`MasterProfile`, stores it in a local vector DB, and writes `master_profile.json`
— the source of truth every later module references.

Phase 2 scores that profile against any job description: it detects the ATS
platform, extracts required vs preferred keywords, and returns a ranked,
actionable gap analysis.

## Quick start

```bash
# 1. (optional) virtual env
python -m venv .venv && .venv\Scripts\activate      # Windows
# source .venv/bin/activate                          # macOS/Linux

# 2. install core deps
pip install -r requirements.txt

# 3. run the pipeline (works with NO API key — uses the heuristic extractor)
python -m job_bot.build_profile

# 4a. open the React dashboard (recommended) — one server serves UI + API
cd web && npm install && npm run build && cd ..   # first time only (builds web/dist)
uvicorn job_bot.api:app --port 8000               # → http://localhost:8000

# 4b. or the classic Streamlit dashboard (run from the project root)
streamlit run job_bot/dashboard.py                # → http://localhost:8501
```

> Full launch recipe (venv activation, the Vite dev server, stopping the server,
> changing the port) is in
> [Phase 9 — the dashboard](#phase-9--the-dashboard-control-center--front-end).

Output lands in `data/`:

- `data/master_profile.json` — structured profile (source of truth)
- `data/raw_text/*.txt` — extracted plain text per document
- `data/chroma/` — local ChromaDB vector store (if ChromaDB is installed)

## Project structure

```
Job Bot/
├── job_bot/          # the Python package (all modules + Streamlit dashboard + FastAPI api.py)
├── web/              # React dashboard (Vite + TS + Tailwind); `npm run build` → web/dist
│                     #   served by job_bot/api.py in single-server mode (see web/README.md)
├── COACH.md          # grounding doc for the Career Coach chat
├── inputs/           # raw source files you drop in — gitignored (PII/credentials)
│                     #   Alumni Spreadsheet.xlsx, Internship & Job Tracker.xlsx,
│                     #   LinkedIn export, linkedin_connections.csv
├── data/             # runtime output — gitignored
│   ├── job_bot.db            # SQLite: applications, connections, emails, interviews…
│   ├── master_profile.json   # structured profile (source of truth)
│   ├── applications/  chroma/  raw_text/
│   └── backups/              # timestamped DB backups
├── documents/        # your resumes / cover letters / transcripts / avatar — gitignored
├── docs/             # project docs: master plan, resume_branding_playbook.md
│   └── prompts/      #   one-off Claude Code prompt specs (see docs/prompts/README.md)
├── README.md  ·  requirements.txt
```

Import your source files (defaults point at `inputs/`):

```bash
python -m job_bot.intake --alumni --tracker      # uses the inputs/ defaults
```

## Better extraction (optional)

Set an Anthropic API key to use Claude instead of the heuristic parser:

```bash
cp .env.example .env        # then edit .env and paste your key
python -m job_bot.build_profile
```

The pipeline auto-detects the key. Force modes with flags:

```bash
python -m job_bot.build_profile --no-llm        # always heuristic
python -m job_bot.build_profile --no-vector     # skip ChromaDB
python -m job_bot.build_profile --docs "C:\path\to\docs"
```

## Phase 2 — score a job description

After building your profile, score it against any JD:

```bash
python -m job_bot.score_job --file path\to\jd.txt
python -m job_bot.score_job --file jd.txt --url https://boards.greenhouse.io/...   # better ATS detection
python -m job_bot.score_job --text "paste a JD here..."
type jd.txt | python -m job_bot.score_job                                          # via stdin
python -m job_bot.score_job --file jd.txt --no-llm   # force heuristic JD parsing
python -m job_bot.score_job --file jd.txt --json     # machine-readable output
```

It prints an overall match score, four platform-weighted subscores, matched vs
missing keywords, and a ranked gap analysis — then saves `data\score_<role>.json`.
A sample JD lives at `data\sample_jd_deloitte_itrisk.txt`.

The `--url` flag improves ATS detection (Workday / Taleo / iCIMS / Greenhouse /
Lever / SuccessFactors), which changes how the score is weighted.

## Phase 3 — should you cold-apply or network first?

First, load your network once (LinkedIn → Settings → Get a copy of your data →
Connections). A demo file is included:

```bash
python -m job_bot.decide --import-connections data\sample_connections.csv
python -m job_bot.decide --list-connections
```

Then get a verdict for any job:

```bash
python -m job_bot.decide --file jd.txt
python -m job_bot.decide --file jd.txt --url https://... --posted 2026-06-27
python -m job_bot.decide --file jd.txt --company "Deloitte" --days 1
```

It runs the Phase 2 score internally, looks up warm contacts at the company,
weighs competition + resume strength + connection leverage + posting recency,
and returns 🟢 cold-apply / 🟡 apply-and-network / 🔴 network-first with the
specific people to contact and next actions. Decisions are logged to
`data\job_bot.db`. On a 🔴 network-first verdict it **auto-drafts a referral
request for every warm contact** (or force it any time with `--referral-pack`).

Your real LinkedIn `Connections.csv` works directly. Add a `Relationship`
column (values like `recruiter`, `pse`, `umd`, `iefs`, `first_degree`) to tag
warmer ties; otherwise everyone imports as a first-degree connection.

## Phase 4 — generate a tailored application

```bash
python -m job_bot.generate --file jd.txt
python -m job_bot.generate --file jd.txt --renderer rendercv   # LaTeX PDF + editable resume.yaml
```

Selects + reorders your strongest JD-relevant bullets (never fabricates),
writes an ATS-clean one-page `resume.docx` + `resume.pdf`, a `cover_letter`, and
a `checklist.md` to `data\applications\<company>_<role>\`, and reports the
before→after ATS lift. Add an API key to have Claude rewrite bullets/letters in
the JD's language (bullet rewrites use the cheap fast model + prompt caching;
see Tune-ups below). `--renderer rendercv` swaps the PDF pipeline for RenderCV:
a git-diffable `resume.yaml` (Overleaf-compatible) typeset with an ATS-safe
single-column theme.

## Phase 5 — search + route job boards

```bash
python -m job_bot.search_jobs --term "IT audit" --location "Washington, DC" --results 15
python -m job_bot.search_jobs --term "data analyst" --remote --linkedin   # add LinkedIn (opt-in)
python -m job_bot.search_jobs --term "IT audit" --force    # bypass the 1-hour re-scrape guard
python -m job_bot.search_jobs --list      # stored jobs ranked by priority
```

Scrapes via JobSpy — **Indeed by default** (the reliable source); LinkedIn,
Glassdoor, Google, and ZipRecruiter are opt-in via `--linkedin` / `--sites`.
Tags each posting by market tier, scores it against your profile, and ranks by
priority into the `jobs` table. Scraping is deliberately gentle: one site at a
time with a delay in between, one backoff retry on rate limits, and a
`scrape_log` that skips identical searches re-run within an hour.

### jobright.ai — your AI-matched recommendations (`job_bot/jobright.py`)

Pulls your personalized jobright.ai matches into the **same** `jobs` table —
scored, routed, and legitimacy-checked exactly like the JobSpy and portal
sources. jobright is login-walled and personalized, so this reads *your*
authenticated session; it never handles your password.

Two auth paths (Playwright is the default and lower ban-risk — a real browser
session looks like you, vs raw HTTP which has a bot-like fingerprint):

```bash
# 1. Playwright (recommended). ONE-TIME login — must be run from YOUR OWN terminal
#    (a browser window can't be launched onto your desktop for you):
python -m job_bot.jobright --login      # opens a browser; log in; it auto-saves the session
python -m job_bot.jobright --save       # then pull anytime, headless, into the pipeline
python -m job_bot.jobright --preview    # fetch + print without saving
python -m job_bot.jobright --show       # run the pull with a visible browser (debug)

# 2. Cookie (lighter, but the cookie expires + is more detectable). Export your
#    jobright session cookie into .env as JOBRIGHT_COOKIE='...' then:
python -m job_bot.jobright --save --method cookie
```

**ToS note:** jobright's terms likely restrict automated access — this is built
for personal, low-volume use of your own account (same posture as the rest of
the scraping here). Keep it gentle.

> **Status / pick up here (2026-07-05):** the module is built and 12 matches were
> already imported via a one-time DOM grab from a logged-in tab (a stopgap; the
> card markup is hashed so it's not durable). The **durable path still needs the
> one-time `--login` above, run from your terminal** — after that, `--save` works
> headless. A `site='jobright'` filter in the dashboard Pipeline tab is a nice
> next step.

## Phase 6 — networking + outreach

```bash
python -m job_bot.network --company Deloitte --role "Technology Risk Analyst"
python -m job_bot.network --company Deloitte --role "..." --all   # referral pack: draft for EVERY contact
python -m job_bot.network --pending        # follow-up queue
```

Finds warm contacts at the company and drafts personalized referral / intro /
follow-up messages on a cadence (logged to the `outreach` table).

```bash
python -m job_bot.network_map     # alumni/network coverage map across companies
```

`network_map` aggregates your connections by company into a coverage score
(warmth + relationship diversity), names who to reach out to first at each, and
flags target companies with weak or zero coverage. Also in the dashboard 🤝
Network tab as a chart.

## Phase 7 — interview prep + mock

```bash
python -m job_bot.interview --story-bank --save
python -m job_bot.interview --questions behavioral --firm big4
python -m job_bot.interview --drill --qtype behavioral --answer "your answer"
python -m job_bot.interview --mock --firm big4 --rounds 5
```

Builds a STAR+ story bank from your real experience, serves a curated question
bank, and scores answers on a rubric (STAR, quantification, ownership, length,
fillers). With an API key, `--mock` runs a live in-character interviewer.

## Phase 8 — assisted application autofill

```bash
python -m job_bot.apply --answers                      # copy-paste answer sheet
python -m job_bot.apply --url "https://..." --headless --screenshot
python -m job_bot.apply --status applied --job-url "https://..."
```

Opens an application URL and fills matching fields from your profile. It **never
auto-submits** (assisted, ToS-safe) — you review and submit. First run once:
`python -m playwright install chromium`.

## Phase 9 — the dashboard (control center / front end)

There are two front ends over the same SQLite/profile data. The **React
dashboard is the recommended one**; the Streamlit app remains as a fallback.

### React dashboard (recommended) — `web/` + FastAPI on port 8000

A Vite + React + TypeScript app (Tailwind v4, shadcn-style components) talking to
a thin FastAPI layer (`job_bot/api.py`) that reuses the same reconciliation,
scoring, and planning logic as everything else — so the numbers match exactly.
In **single-server mode** FastAPI serves the built UI *and* the JSON API from one
process:

```powershell
# Windows PowerShell — from the project root
cd "C:\ClaudeProjects\Job Bot"
cd web; npm install; npm run build; cd ..    # first time only → web/dist
uvicorn job_bot.api:app --port 8000          # → http://localhost:8000
```

While editing the UI, run the Vite dev server instead (hot reload); it proxies
`/api/*` to the backend so you run both:

```bash
uvicorn job_bot.api:app --reload --port 8000   # terminal 1 — API
cd web && npm run dev                           # terminal 2 — UI on :5173
```

**13 pages behind a grouped sidebar** (collapses to a drawer on narrow
viewports; the active page persists via `localStorage`):

- **Overview** — Overview (KPIs + funnel + field mix + profile), **Coach**
  (LLM career chat grounded in your live pipeline)
- **Pipeline** — Applications, Pipeline, Find Jobs (job-board picker seeded
  from `/api/cycles` `default_sites`, results-per-role slider 5–50)
- **Build** — **Resume Studio** (edit the RenderCV YAML as text, typeset to a
  Typst PDF, download `.pdf`/`.yaml`/`.typ` or the classic `.docx`),
  Score a JD, LinkedIn
- **Network & Growth** — Network, Growth, Offers, Company Brief, Interview Lab

Every page follows one action pattern: a single primary button (bottom-right
of its card, `Loader2` + verb-ing label while running); secondary actions are
`outline`/`ghost` or icon-only. API/action failures render through the shared
`ErrorNote` panel. Details + the endpoint map are in
[`web/README.md`](web/README.md).

### Streamlit dashboard (classic)

**Launch it from a fresh terminal** (copy-paste the whole block):

```powershell
# Windows PowerShell
cd "C:\ClaudeProjects\Job Bot"
.\.venv\Scripts\Activate.ps1        # skip if you're not using a venv
streamlit run job_bot/dashboard.py
```

```bash
# macOS / Linux / Git Bash
cd "/c/ClaudeProjects/Job Bot"       # adjust to your path
source .venv/bin/activate            # skip if you're not using a venv
streamlit run job_bot/dashboard.py
```

Streamlit prints a Local URL (default **http://localhost:8501**) and opens it in
your browser. Leave the terminal running; press **Ctrl+C** in it to stop the
server. If port 8501 is busy, add `--server.port 8502`.

Run the command **from the project root** (`Job Bot/`), not from inside
`job_bot/` — `dashboard.py` puts the project root on `sys.path` itself, so the
`streamlit run job_bot/dashboard.py` form above works from a clean shell.

The visual front end that tracks everything. Tabs:

- **🏠 Action Center** — the home view: counts (active apps, upcoming
  interviews, follow-ups due, open offers, rejections) + live lists of what
  needs attention today (interviews, follow-ups, unhandled recruiter emails,
  open offers, top new postings). This is the "what's going on" screen.
- **✅ Applications** — the canonical application tracker: one deduped,
  field-classified row per position applied, reconciled across the jobs table,
  Gmail outcome history, and the imported spreadsheet tracker.
- **📋 Overview** — profile, education, experience, skills.
- **📈 Growth Plan** — automated certs / portfolio projects / resume-variant
  plan recomputed from your live skill gaps and where you're actually applying.
- **🔎 Find Jobs** — search job boards by **hiring cycle** (derived from your
  graduation date: e.g. Fall 2026 / Spring 2027 internships, Summer 2027 full-time)
  and **career track** (Accounting & Audit, Finance & FP&A, Data & Analytics,
  IT & Cybersecurity, **Software & Engineering** — pick tech, business, or both).
  Shows rich results: found/on-target/new counts, by-field + by-tier charts, a
  per-search breakdown, and top-match cards. Off-target ("Other") roles are hidden
  by default. Set your graduation date here; it saves back to `master_profile.json`.
- **📊 Pipeline** — ranked jobs, decision log, rejection analytics.
- **🤝 Network** — connections + outreach follow-up queue.
- **💰 Offers** — log offers and compare them COL-adjusted with priority sliders.
- **⚡ Score a JD** — runs Phases 2–3 (ATS + network verdict) live.
- **🏢 Company Brief** — pre-interview research brief on demand.
- **💼 LinkedIn** — profile optimizer audit (headline, About, skills vs ATS logic).
- **🎤 Interview Lab** — recording analysis: pacing, fillers, STAR compliance.

## How it works

```
job_bot/
  config.py          settings, paths, API-key detection
  models.py          Pydantic v2 MasterProfile schema
  ingest.py          PDF / DOCX / TXT readers -> raw text
  extract.py         LLM extractor (Claude) + heuristic fallback
  store.py           ChromaDB vector store (optional)
  build_profile.py   Phase 1 CLI

  skills_ontology.py canonical skills, synonyms, role/market/ATS/company signals
  jd_models.py       JobPosting + ATSScoreReport models
  jd_parser.py       JD -> structured JobPosting
  ats_platforms.py   ATS detection + per-platform scoring weights/tips
  similarity.py      pure-Python TF-IDF cosine (optional transformers upgrade)
  ats_engine.py      reverse ATS scoring + ranked gap analysis
  score_job.py       Phase 2 CLI

  db.py              SQLite store (connections, decisions, jobs, outreach)
  connections.py     LinkedIn CSV import + per-company leverage scoring
  decision_models.py decision report models
  decision_engine.py competition + resume + leverage -> 🟢/🟡/🔴 verdict
  decide.py          Phase 3 CLI

  resume_models.py   tailored resume models
  tailor.py          bullet selection + reorder + optional Claude rewrite
  render_docx.py     ATS-clean DOCX renderer
  render_pdf.py      ATS-clean PDF renderer (reportlab)
  render_rendercv.py resume -> RenderCV YAML -> LaTeX PDF (--renderer rendercv)
  cover_letter.py    JD-mirroring cover letter (facts-only)
  generate.py        Phase 4 CLI

  routing.py         market-tier + platform routing + priority score
  jobsearch.py       JobSpy wrapper + score/route
  search_jobs.py     Phase 5 CLI
  jobright.py        jobright.ai AI-matched jobs -> pipeline (Playwright/cookie)

  outreach.py        personalized message drafting
  networking.py      contact lookup + cadence scheduling
  network.py         Phase 6 CLI

  interview_models.py  Story / Question / AnswerScore models
  story_bank.py        STAR+ story extraction
  questions.py         curated question bank
  rubric.py            answer scoring
  interview.py         Phase 7 CLI

  autofill.py        profile -> form fields, Playwright assisted fill
  apply.py           Phase 8 CLI

  dashboard.py       Phase 9 Streamlit dashboard
  ui.py              dashboard design system (components, theme)
  api.py             FastAPI JSON layer for the React dashboard (also serves web/dist)
  coach.py           Career Coach — live-pipeline snapshot + grounded LLM chat

  intake.py          import personal spreadsheets (alumni workbook, job tracker)
  gmail_sync.py      Gmail MCP threads -> classified, deduped pipeline updates
  applications.py    canonical deduped application tracker (source of truth)
  growth.py          automated growth plan (certs / projects / resume variants)
  newgrad.py         entry-level multi-board search sweep (newgrad-jobs style)
  seniority.py       role-level detection; filters senior+ roles out of the pipeline

  legitimacy.py      ghost-job / scam check + Playwright liveness verify
  portals.py         direct career-portal scan (Greenhouse/Lever feeds)
  negotiation.py     paste-ready salary-negotiation scripts
  transcript.py      UMD transcript parser -> education enrichment
  inbox.py           recruiting-email triage -> status + next action
  prep_plan.py       interview prep schedule -> calendar events / .ics
  thankyou.py        post-interview thank-you drafts
  company_research.py pre-interview company brief (curated intel + DB + news)
  offers.py          COL-adjusted, priority-weighted offer comparison
  salary.py          market salary range + offer-vs-market assessment
  network_map.py     alumni/network coverage map across target companies
  linkedin_optimizer.py LinkedIn headline/About/skills audit vs ATS logic
  cover_ab.py        cover-letter A/B variants + response-rate learning
  notify.py          fresh-job / deadline / follow-up alerts (+ Slack webhook)
  recording.py       interview-recording analysis (pacing, fillers, STAR)
  rejections.py      rejection logging + pattern analysis
  pipeline.py        Tracking & comms CLI (--inbox/--prep-plan/--thankyou/--brief/--rejections/--queue)
```

Source documents live in `documents/` (kept out of the code package and
git-ignored); generated artifacts go to `data/`.

## Tracking & communications (recommendations layer)

```bash
python -m job_bot.pipeline --inbox-demo                       # triage sample recruiting emails
python -m job_bot.pipeline --prep-plan --company Deloitte --role "IT Risk" --firm big4 --date 2026-07-15 --ics
python -m job_bot.pipeline --thankyou --company Deloitte --interviewer "Marcus Webb" --topics "ITGC, AI risk"
python -m job_bot.pipeline --queue                            # unified "what needs action today"
python -m job_bot.pipeline --log-rejection --company PwC --stage ats_screen
python -m job_bot.pipeline --rejections                       # rejection-pattern analysis
python -m job_bot.pipeline --brief --company Deloitte --role "Technology Risk" \
    --news "headline 1" --news "headline 2"                   # pre-interview company brief
```

Rejections auto-log from inbox triage (or `--log-rejection`) and
`--rejections` surfaces patterns — which stage rejects you most, at what ATS
score, and which role types — with targeting recommendations.

### Offer comparison

```bash
python -m job_bot.offers --add --company Deloitte --base 78000 --bonus 6000 \
    --benefits 9000 --location "Arlington, VA" --growth 4 --fit 5 --deadline 2026-08-15
python -m job_bot.offers --add --company "Goldman Sachs" --base 95000 --bonus 15000 \
    --location "New York, NY"
python -m job_bot.offers --compare                       # COL-adjusted, weighted ranking
python -m job_bot.offers --compare --w-money 0.7 --w-fit 0.2 --w-growth 0.1
```

Logs competing offers and ranks them by **cost-of-living-adjusted** total comp
weighted by your own money/growth/fit priorities — so a higher nominal NYC offer
can correctly lose to a remote one with better purchasing power. Also lives in
the dashboard's 💰 Offers tab with interactive priority sliders.

### Notifications (fresh jobs / deadlines / follow-ups)

```bash
python -m job_bot.notify --max-age 24 --min-priority 60        # console alerts
python -m job_bot.notify --tier 1 --webhook https://hooks.slack.com/...   # + Slack push
python -m job_bot.notify --dry-run                             # preview without recording
```

Alerts on high-priority postings scraped within the last N hours, offer
deadlines, and overdue follow-ups — deduped so each fires once. Add a
Slack-compatible webhook (or set `JOB_BOT_WEBHOOK`) and schedule it (Task
Scheduler / cron) to get pushed the moment a competitive role appears.

### Interview recording analysis

```bash
python -m job_bot.recording --demo                            # filler-heavy sample
python -m job_bot.recording --file answer.txt --duration 95   # pacing needs duration
python -m job_bot.recording --session session.json            # whole practice set
```

Turns a recorded-answer transcript into measurable feedback: words-per-minute
pacing, fillers per minute, STAR compliance, and the exact filler/hedge phrases
to cut. Session mode aggregates a full practice set. Also in the dashboard 🎤
Interview Lab tab.

### Cover-letter A/B testing

```bash
python -m job_bot.cover_ab --file jd.txt --company Deloitte --firm-type big4
python -m job_bot.cover_ab --sent 1                 # mark variant #1 as sent
python -m job_bot.cover_ab --response 1 interview   # outcome: none | reply | interview
python -m job_bot.cover_ab --analyze                # best-performing voice
```

Generates two variants — formal/finance-led (A) vs conversational/tech-led (B) —
logs them, and after you record outcomes learns which voice converts best per
firm type. Analysis also shows in the dashboard Pipeline tab.

### LinkedIn profile optimizer

```bash
python -m job_bot.linkedin_optimizer                          # uses your default target role
python -m job_bot.linkedin_optimizer --file jd.txt           # find keyword gaps vs a JD
python -m job_bot.linkedin_optimizer --role "Data Analyst"
```

Audits your profile with the same ATS keyword logic and produces paste-ready
LinkedIn edits: a length-capped headline, an About draft, a priority-ranked
skills list (JD gaps first), per-role bullets to mirror, and a checklist. Also
in the dashboard 💼 LinkedIn tab.

### Salary intelligence

```bash
python -m job_bot.salary --role "IT audit" --location "Washington, DC" --level analyst
python -m job_bot.salary --role "data analyst" --location "New York, NY" \
    --offer 95000 --market 104000 --market 91000      # assess an offer vs live market
```

Returns a COL-adjusted 25th/50th/75th-percentile total-comp range for the role +
location + level, and (with `--offer`) positions your offer against it with a
below/at/above-market verdict and a negotiation target. Curated baselines work
offline; pass real `--market` figures (Glassdoor / Levels.fyi / LinkedIn) to
ground the range. Also lives in the dashboard 💰 Offers tab.

`--brief` builds a one-page pre-interview company brief: hiring process, ATS
platform, firm values, "why this firm" angles tuned to your background, likely
interview topics, your warm contacts there, any prior history, and smart
questions to ask. Curated firm intel works offline; pass real headlines via
`--news` (from web search or a news MCP) to ground the "why this firm" pitch.

Inbox triage classifies recruiter emails (invite / assessment / reply /
rejection / offer), advances the matching job's status, and feeds the action
queue. The prep planner emits Google Calendar-ready events + an `.ics` file.
Wire your Gmail/Calendar (re-auth the MCPs) to run these live.

## Posting quality: legitimacy, apply gate, portal scan (career-ops layer)

Adapted from [career-ops](https://github.com/santifer/career-ops)'s quality-over-
quantity philosophy — don't waste an application on a scam or a role that isn't
really open. These run automatically on every scraped/portal job and surface in
the dashboard 📊 Pipeline tab (a `legit` grade, an `apply?` gate column, a
Recommendation filter, and a flagged-postings callout).

```bash
# Legitimacy: flag scam (fee-upfront, WhatsApp interview, gift-card pay) + ghost
# (evergreen "always hiring", stale-but-open, thin) postings. Negation-aware, so a
# bank teller who "processes wire transfers" and anti-scam disclaimers aren't flagged.
python -m job_bot.legitimacy --file jd.txt --company "Acme" --days 45
python -m job_bot.legitimacy --file jd.txt --verify-url "https://..."   # + Playwright liveness

# Direct career-portal scan: pull fresh openings straight from company portals via
# public Greenhouse/Lever feeds (fresher than aggregators); Workday/Taleo portals
# with no public feed return a direct link + strategy. Extend via data/portals.json.
python -m job_bot.portals             # preview matching roles + manual portals
python -m job_bot.portals --save      # score, legitimacy-check, and add to the pipeline
```

The **apply gate** (`routing.recommend`) is gated to who you actually are, in
order: **seniority** (a senior/manager role is 🎓 Above level — never "Apply" for an
entry-level candidate; a mid-level role caps at "Maybe") → **legitimacy** → **field
fit** (a role outside your target fields is never a clean "Apply") → **priority**
(tier + ATS fit + recency). Seniority (`seniority.py`, reads title markers + the
"N years" required in the JD) also **filters senior/lead/exec roles out of search
results entirely** — so 'Staff Accountant' (entry) stays but 'Senior Auditor' /
'Audit Manager' / 'Analyst III' never reach the pipeline. The dashboard Pipeline tab
has a **Level filter** (defaults to "My level (intern–mid)") and shows each role's
level on its card.

### Salary negotiation scripts

```bash
python -m job_bot.negotiation --role "IT audit" --location "Washington, DC" --offer 72000
python -m job_bot.negotiation --role "data analyst" --offer 80000 --competing 88000
```

Turns the salary estimate into paste-ready scripts — a data-anchored counter,
geographic-discount pushback, competing-offer leverage, non-cash asks, and a
counter email. Also in the dashboard 💰 Offers tab. (The salary engine now dampens
the cost-of-living-to-pay conversion, since pay tracks COL only partially.)

## Tune-ups (implemented 2026-07-02)

The three workstreams from
[`docs/prompts/tuneups_adjustments.md`](docs/prompts/tuneups_adjustments.md) are
**done**:

1. **Safer scraping** (`jobsearch.py` / `search_jobs.py`) — `--sites` defaults
   to **Indeed only** (add `--linkedin` to opt in); sites are scraped one at a
   time with a 3s inter-site delay; a rate-limit-shaped failure (429) waits 45s
   and retries once before giving up cleanly; and every search is logged to a
   `scrape_log` table so re-running the same term+location within an hour warns
   and skips (`--force` overrides). Personal-use, low-volume, unauthenticated —
   by design.
2. **Cheaper LLM calls** (`tailor.py` / `cover_letter.py`) — bullet rewriting
   (mechanical) routes to Haiku via `ANTHROPIC_MODEL_FAST`; the cover letter
   (judgment) stays on the full model. Both prompts are split into a cacheable
   profile block (`cache_control`, deterministic serialization) + a small
   per-job block — verified: the 2nd `generate` in a session reads the profile
   from cache (`cache_read=1228` tokens at ~10% price). `max_tokens` is sized
   to the actual expected output, and every call prints its token usage so
   cost is never invisible.
3. **LaTeX/Overleaf resume pipeline** (`render_rendercv.py`) —
   `python -m job_bot.generate --file jd.txt --renderer rendercv` maps the
   tailored resume into RenderCV YAML (written next to the PDF as
   `resume.yaml` — git-diffable, opens in Overleaf) and renders via the
   ATS-safe `engineeringresumes` theme (single column, no icons). Verified:
   one page, clean text extraction (0 glyph issues), keyword parity with the
   docx renderer. Falls back to the reportlab PDF if `rendercv` isn't
   installed. Default renderer remains `docx`.

The reportlab PDF renderer (`render_pdf.py`) now **auto-fits one page**: if the
content overflows, it re-renders at progressively tighter type/spacing down to a
readable floor, so a slightly longer profile stays one page without hand-tuning.

A regression test (`tests/test_pipeline.py`) runs the tailoring pipeline against
the fixture JD and asserts all three renderers (docx / reportlab PDF / RenderCV
PDF) produce a valid one-page file with a clean, parseable text layer:

```bash
python -m tests.test_pipeline      # plain script, no pytest needed
python -m pytest tests/            # also pytest-compatible
```

Still pending: re-auth the Gmail / Google Calendar MCPs so inbox triage and the
prep planner run live instead of on demo data.

## Graceful degradation

Everything runs on a fresh clone:
- **No `ANTHROPIC_API_KEY`** → heuristic extraction / parsing / bullet selection
  (set a key to upgrade quality via Claude).
- **No ChromaDB / JobSpy / Playwright** → vector store, live scraping, and
  browser autofill (and posting-liveness verify) are skipped with a clear
  message; the rest still works.
- **No `requests` / no network** → the career-portal scan returns the manual
  portal links only; the legitimacy text-check still runs offline.
- **No sentence-transformers / spaCy** → pure-Python TF-IDF cosine is used.
- **No rendercv** → `--renderer rendercv` falls back to the reportlab PDF with
  a clear message (`pip install "rendercv[full]"` to enable).

See [`docs/job_application_system_master_plan.md`](docs/job_application_system_master_plan.md)
for the full build log and Python 3.14 environment notes.
