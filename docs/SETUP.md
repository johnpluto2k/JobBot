# Setting up Job Bot for yourself

This is the manual walkthrough. If you have Claude Code, the faster route is to
open it at the repo root and paste [`SETUP_PROMPT.md`](SETUP_PROMPT.md), which
performs these steps interactively and verifies each one.

To look around first, `python -m job_bot demo` runs the dashboard on fictional
data with no keys and none of the steps below.

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
pip install -r requirements.txt   # core: dashboard, tracker, watcher, tailoring, coach, tests
```

The core install is an editable install of this folder (`pip install -e .`),
so `git pull` is all an update needs. Optional features are separate, and each
is imported only when used:

| Feature | Install |
| --- | --- |
| RenderCV / Typst résumé renderer | `pip install -e ".[rendercv]"` |
| Browser autofill, posting-liveness checks | `pip install -e ".[browser]"`, then `python -m playwright install chromium` |
| Find Jobs multi-board search | `pip install -e ".[search]"` |
| Legacy Streamlit dashboard, vector store | `pip install -e ".[legacy]"` |
| All of the above | `pip install -r requirements-extras.txt` |

Python 3.14 note: `python-jobspy` (Find Jobs) pins an old numpy with no 3.14
wheel, so the `search` extra skips it there. Install it without its
dependencies instead:

```bash
pip install --no-deps python-jobspy
pip install tls_client markdownify beautifulsoup4 requests regex
```

`python -m job_bot doctor` lists what is installed and configured at any point.

## 2. Environment

```bash
cp .env.example .env
```

Fill in what you have. `ANTHROPIC_API_KEY` upgrades extraction and enables the
writing features and the dashboard coach. Set `JOB_BOT_HOME_MARKERS` to the
city and state words that count as "home" for you, for example
`JOB_BOT_HOME_MARKERS=chicago,il,illinois,evanston,naperville`. Remote and
nationwide postings always pass the filter.

## 3. Google sign-in and Gmail sync (optional)

Skip this section and the dashboard opens in **local mode**: no sign-in,
requests accepted from this machine only, and you log applications by hand.
Come back to it when you want the tracker to fill itself from recruiter email.

With an OAuth client configured, the dashboard is gated behind Google sign-in
and reads job-related Gmail every 15 minutes. Both use one client with
read-only scope. The app never sends, labels, or deletes mail.

1. In [Google Cloud Console](https://console.cloud.google.com/) create a project
   and enable the **Gmail API**.
2. Configure the OAuth consent screen (**Google Auth Platform → Audience**):
   user type External, add your own Gmail address as a test user, then click
   **Publish app** so the publishing status reads **In production**. In
   *Testing* status Google expires the refresh token **7 days** after each
   sign-in and sync silently stops. A personal, unverified app in production
   is fine: Google shows a "Google hasn't verified this app" screen at sign-in
   (choose *Advanced → Go to … (unsafe)*). The app only runs on your machine
   and its client secret stays in your `.env`.
3. Create an **OAuth 2.0 Client ID** of type *Web application* with
   `http://localhost:8000/auth/callback` as an authorized redirect URI.
4. Put the client id and secret in `.env` as `GOOGLE_CLIENT_ID` and
   `GOOGLE_CLIENT_SECRET`.

At sign-in, **tick every permission box**, including *View your email messages
and settings*. Google lets you untick individual scopes; a login without the
Gmail one signs you in to the dashboard but cannot sync.

The refresh token, session, and sync status land under `data/` (gitignored).
When sync fails because the login expired, was revoked, or lacks Gmail
permission, the header's sync chip and the Coach tab show a **Reconnect
Google** link with the reason.

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
python -m job_bot serve          # builds the UI the first time, then http://localhost:8000
```

After a UI change, rebuild with `cd web && npm run build`. To run the pieces
yourself: `uvicorn job_bot.api:app --port 8000`, and `npm run dev` in `web/`
for the Vite dev server.

If you set up Google, sign in; the header chip shows the last Gmail sync and
**sync now** runs one immediately. In local mode the header says so instead.
Either way, use **Applications → Log an application** every time you apply.

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
python -m job_bot doctor         # what is set up, what is missing
python -m pytest                 # offline tests, a few seconds
python coach_snapshot.py .       # JSON with a "freshness" block and your funnel
python -m job_bot.watch --dry-run
```

Then read [`PERSONALIZATION.md`](PERSONALIZATION.md) for the handful of files
still tuned to the original owner's field.
