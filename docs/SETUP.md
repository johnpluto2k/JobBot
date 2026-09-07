# Setting up Job Bot for yourself

This is the manual walkthrough. If you have Claude Code, the faster route is to
open it at the repo root and paste [`SETUP_PROMPT.md`](SETUP_PROMPT.md), which
performs these steps interactively and verifies each one.

Nothing personal ships with the repo. Everything you create below
(`.env`, `documents/`, `data/`, `COACH.md`, `COACH_STATE.md`) is gitignored, so
you can keep your fork public without leaking anything.

## 1. Toolchain

| Tool | Version | Why |
| --- | --- | --- |
| Python | 3.12+ (developed on 3.14) | the whole backend |
| Node.js | 20+ | builds the React dashboard once |
| git | any recent | the launcher fast-forwards from `main` |
| Claude Code | current | coaching mode, the daily pipeline, the guided setup |
| Chrome + [Claude in Chrome](https://claude.com/chrome) | current | lets Claude read job boards and your Overleaf project |
| Anthropic API key | optional | LLM extraction, tailoring, cover letters, dashboard coach |
| Google Cloud project | optional | Sign in with Google + read-only Gmail sync |

```bash
git clone <your fork> "Job Bot" && cd "Job Bot"
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Python 3.14 notes: `python-jobspy` (the Find Jobs scraper) pins an old numpy
with no 3.14 wheel. Install it without deps if you want Find Jobs:

```bash
pip install --no-deps python-jobspy
pip install tls_client markdownify beautifulsoup4 requests regex
```

For the RenderCV/Typst résumé renderer: `pip install "rendercv[full]"`. For
browser autofill and posting-liveness checks: `python -m playwright install chromium`.

## 2. Environment

```bash
cp .env.example .env
```

Fill in what you have. `ANTHROPIC_API_KEY` upgrades extraction and enables the
writing features and the dashboard coach. Set `JOB_BOT_HOME_MARKERS` to the
city and state words that count as "home" for you, for example
`JOB_BOT_HOME_MARKERS=chicago,il,illinois,evanston,naperville`. Remote and
nationwide postings always pass the filter.

## 3. Google sign-in and Gmail sync

The dashboard is gated behind Google sign-in, and the tracker fills itself from
recruiter email. Both use one OAuth client with read-only scope. The app never
sends, labels, or deletes mail.

1. In [Google Cloud Console](https://console.cloud.google.com/) create a project
   and enable the **Gmail API**.
2. Configure the OAuth consent screen (External, testing mode, add your own
   Gmail address as a test user).
3. Create an **OAuth 2.0 Client ID** of type *Web application* with
   `http://localhost:8000/auth/callback` as an authorized redirect URI.
4. Put the client id and secret in `.env` as `GOOGLE_CLIENT_ID` and
   `GOOGLE_CLIENT_SECRET`.

The refresh token, session, and sync status land under `data/` (gitignored).
If sync later fails with `invalid_grant`, the dashboard shows a **Reconnect
Google** link; testing-mode consent expires periodically.

## 4. Your documents and profile

Create `documents/` at the repo root and drop in your résumés, cover letters,
transcripts, and project write-ups (PDF, DOCX, TXT, or Markdown). Then:

```bash
python -m job_bot.build_profile          # add --no-llm to force the heuristic parser
```

Open `data/master_profile.json` and check the fields everything else depends
on: `personal.name`, `education[0].school`, `education[0].major`,
`education[0].graduation_date` (for example `"May 2027"`), and
`targets.target_roles` / `targets.target_firms`. Fix by hand if extraction
guessed wrong. `job_bot.candidate` reads these fields to fill every prompt,
letter, and sign-off, so this is where "your information" comes from.

Optional: import your LinkedIn connections export (LinkedIn → Settings → Get a
copy of your data → Connections):

```bash
python -m job_bot.decide --import-connections Connections.csv
```

Add a `Relationship` column to tag warmer ties (`recruiter`, `alum`,
`first_degree`, or your own tags). Your own tags get a phrase in
`data/affiliations.json`, for example `{"rowing": "as a fellow rowing alum"}`.

## 5. Coaching files

```bash
cp templates/COACH.template.md COACH.md
cp templates/COACH_STATE.template.md COACH_STATE.md
```

Fill in `COACH.md`: who you are, what you are targeting, any constraints the
coach must respect. Leave `COACH_STATE.md` mostly empty; the coach fills it as
sessions happen. Both are gitignored. If you use git worktrees, keep them in
the primary checkout, which is where `config.DATA_HOME` points.

Then run the first session:

```bash
claude        # in the repo folder; ask "where are we?"
```

## 6. Dashboard

```bash
cd web && npm install && npm run build && cd ..     # first time, and after UI changes
uvicorn job_bot.api:app --port 8000                  # http://localhost:8000
```

Sign in with Google. The header chip shows the last Gmail sync; **sync now**
runs one immediately. Use **Companies → Log a job** every time you apply.

On Windows with [Orca](https://orca.dev) installed, `start-job-bot.cmd` does all
of this and opens the coach terminal alongside. Without Orca, run
`scripts\run-server.cmd` and `scripts\career-coach.cmd` in two terminals. All
scripts locate the repo from their own path.

## 7. Overleaf

Many people keep the master résumé as a LaTeX project in Overleaf (the
"Jake's Resume" template is a common starting point) and work **bullets-first**:
the bot proposes tailored bullets, you paste them into Overleaf and keep control
of layout. To set that up:

1. Sign in to [Overleaf](https://www.overleaf.com) in Chrome and create or
   upload your master résumé project. Treat it as the superset you trim from.
2. Export a PDF of it into `documents/` so `build_profile` ingests the same
   content the résumé shows.
3. Record the project URL under "Operating rules" in `COACH_STATE.md`, so the
   coach knows where the canonical résumé lives.
4. When Claude in Chrome is connected (next step), Claude can open the project,
   read the source, and hand back bullets that fit the line width. Ask it to
   measure line fit rather than guess character counts.

## 8. Claude in Chrome

1. Install the extension from <https://claude.com/chrome> and sign in.
2. In the extension's site permissions, allow the sites you want Claude to read:
   `overleaf.com`, `linkedin.com`, `indeed.com`, `joinhandshake.com`, and any
   company career sites you use.
3. In Claude Code, ask it to "list my Chrome tabs". If it can, the MCP
   connection works. It will open job boards in new tabs, read them, and
   summarize; it never applies on your behalf.

## 9. Company tracker seed (optional)

Companies are created automatically the first time you log a job at one. To
start with a target list, edit `scripts/seed_broad_targets.py` (the shipped list
is the original owner's, weighted toward accounting, GRC, and the DC area) and
run it with `--dry-run` first. To have the watcher poll a company, its board
token must be verified live and added to `job_bot/watch_registry.py`.

## 10. Check

```bash
python -m pytest                 # 92 offline tests
python coach_snapshot.py .       # JSON with a "freshness" block and your funnel
python -m job_bot.watch --dry-run
```

Then read [`PERSONALIZATION.md`](PERSONALIZATION.md) for the handful of files
still tuned to the original owner's field.
