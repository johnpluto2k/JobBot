# Guided setup prompt

Open Claude Code at the root of this repo and paste everything below the line.
It walks a new owner through the full stack: toolchain, environment, Google
OAuth, documents and profile, private coaching files, the dashboard, Overleaf,
and the Claude in Chrome extension. It asks before doing anything that touches
accounts or keys, and it never commits personal files.

---

You are setting up **Job Bot** for me, a new owner of this repo. I am not the
person who built it, so nothing here should assume their name, school, field,
or location. Read `README.md`, `docs/SETUP.md`, and `docs/PERSONALIZATION.md`
first, then work through the steps below in order. After each step, show me
the evidence it worked (command output, a file path, a screenshot description)
before moving on. If a step needs something only I can do (paste a key, click
a consent screen, sign in), tell me exactly what to do and wait.

Ground rules for this whole session:

- Never commit, print, or echo the contents of `.env`, `data/`, `documents/`,
  `COACH.md`, or `COACH_STATE.md`. Confirm with `git status` at the end that
  none of them are tracked.
- Never send email, submit an application, or post anything on my behalf.
- If a command fails, show me the error and fix it; don't skip the step.

**Step 1 — Toolchain.** Check `python --version` (3.12+), `node --version`
(20+), `git --version`, and that `claude` is on PATH. Create `.venv`, activate
it, and `pip install -r requirements.txt`. On Python 3.14 install
`python-jobspy` with `--no-deps` plus its runtime deps as `docs/SETUP.md`
describes. Offer `pip install "rendercv[full]"` and
`python -m playwright install chromium` as optional extras and let me decide.

**Step 2 — Environment.** Copy `.env.example` to `.env`. Ask me for my
Anthropic API key (I'll paste it directly into `.env` myself if I prefer). Ask
which city and state words count as "home" for me and set
`JOB_BOT_HOME_MARKERS`. Leave the Google fields for step 3.

**Step 3 — Google sign-in and Gmail.** Explain in five short steps how to
create a Google Cloud project, enable the Gmail API, set up an External consent
screen in testing mode with my address as a test user, and create a *Web
application* OAuth client with `http://localhost:8000/auth/callback` as the
redirect URI. Wait for me to paste the client id and secret into `.env`.
Confirm the scopes in `job_bot/google_auth.py` are read-only.

**Step 4 — Documents and profile.** Create `documents/`. Ask me to drop in my
résumés, cover letters, transcripts, and project write-ups, then run
`python -m job_bot.build_profile`. Open `data/master_profile.json` and walk me
through the fields everything depends on: `personal.name`,
`education[0].school`, `education[0].major`, `education[0].graduation_date`,
`targets.target_roles`, `targets.target_firms`, `targets.target_markets`. Fix
anything the extractor got wrong. Then run
`python -c "from job_bot import candidate; print(candidate.name(), '|', candidate.blurb())"`
and show me that it describes me, not the original owner. If I have a
LinkedIn connections export, import it with
`python -m job_bot.decide --import-connections <file>` and help me set up
`data/affiliations.json` for any custom relationship tags.

**Step 5 — Coaching files.** Copy `templates/COACH.template.md` to `COACH.md`
and `templates/COACH_STATE.template.md` to `COACH_STATE.md`. Interview me
briefly (five or six questions, one at a time) about who I am, what roles and
employers I'm targeting, my location and remote preference, my weekly
application target, and any hard constraints (graduation date rules,
relocation limits, visa timing). Write my answers into `COACH.md` in the
template's structure, keeping the balanced tone section as is. Put a first
START HERE agenda with two or three items into `COACH_STATE.md`. Confirm both
files are gitignored.

**Step 6 — Dashboard.** Run `cd web && npm install && npm run build && cd ..`,
then start `uvicorn job_bot.api:app --port 8000` in the background. Ask me to
open `http://localhost:8000`, sign in with Google, and click **sync now** in
the header. Then check `GET /api/health` and `GET /api/sync-status` and tell
me whether the first sync succeeded. If it failed with `invalid_grant` or a
consent error, explain the Reconnect Google link.

**Step 7 — Claude in Chrome.** Ask me to install the Claude in Chrome
extension from <https://claude.com/chrome>, sign in, and grant it access to
`overleaf.com`, `linkedin.com`, `indeed.com`, `joinhandshake.com`, and the
career sites I use. Then call the browser tools yourself: list my open tabs,
open one job board in a new tab, and read its text back to me in two
sentences. If the tools aren't available, tell me what's missing rather than
guessing.

**Step 8 — Overleaf.** Ask me to sign in to Overleaf in Chrome and either open
my existing master résumé project or create one (offer the Jake's Resume
template as a starting point). Using the browser tools, open the project and
read the source so you can confirm you can see it. Explain the bullets-first
workflow: the master résumé in Overleaf is the superset I trim from; the bot
proposes tailored bullets; I paste them in and own the layout; bullets must
fill the line, measured, never guessed. Ask me to export a PDF of the master
résumé into `documents/`, rerun `build_profile`, and record the project URL
under "Operating rules" in `COACH_STATE.md`.

**Step 9 — Company tracker.** Explain that companies are created automatically
when I log a job. Show me `scripts/seed_broad_targets.py`, explain that its
list is the original owner's, and help me replace it with 20–40 employers I
actually care about, grouped the same way. Run it with `--dry-run`, then for
real if I approve. Run `python -m job_bot.watch --dry-run` and explain which
companies the watcher can and cannot poll, and how a board token gets added to
`job_bot/watch_registry.py` only after being verified live.

**Step 10 — Personalization pass.** Read `docs/PERSONALIZATION.md` and go
through its "tune to your field" list with me: search tracks and queries in
`job_bot/newgrad.py`, the watcher keywords, the skills ontology, the curated
company intel, cost-of-living indices, and the cover-letter template
vocabulary. For each, tell me in one sentence whether it already fits my field
or what you'd change, and make the changes I approve.

**Step 11 — Verify and hand off.** Run `python -m pytest` and report the
result honestly. Run `python coach_snapshot.py .` and confirm the `freshness`
block reflects the sync from step 6. Run `git status` and confirm no private
file is tracked. Show me how to start everything day to day (`start-job-bot.cmd`
on Windows with Orca, or `scripts/run-server.cmd` plus `scripts/career-coach.cmd`).
Finish by switching into coaching mode as `CLAUDE.md` describes: deliver the
START HERE briefing you wrote in step 5 and ask me which agenda item to take
first.
