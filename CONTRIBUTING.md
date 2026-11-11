# Contributing

Job Bot started as one person's job-search tool and is still shaped by that
search. Fixes, new ATS fetchers, and anything that makes it work for a field
other than accounting and audit are all welcome.

## Get a working copy

```bash
git clone https://github.com/johnpluto2k/JobBot.git && cd JobBot
python -m venv .venv
.venv\Scripts\activate              # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt     # core + test tools
python -m job_bot demo              # dashboard on fictional data, no keys needed
```

`python -m job_bot demo` writes to `demo_data/` and never touches `data/`, so it
is the safe place to try a change. `python -m job_bot doctor` shows what is and
isn't set up.

## Before you open a pull request

```bash
python -m pytest                    # all offline, a few seconds
cd web && npm run lint && npm run build
```

CI runs the same two steps on Python 3.12 and 3.13.

- Add a test for a bug fix. Most of the suite is regression tests named after
  the real misread they prevent (an assessment filed as a rejection, a receipt
  counted as an interview); follow that pattern.
- Tests must not need a network connection, an API key, or anyone's real data.
  Use the fixtures that point `config.OUTPUT_DIR` and `db.DB_PATH` at
  `tmp_path`, and `job_bot.demo.PROFILE` when you need a profile.
- Keep one topic per pull request and say what you ran.

## Rules the code depends on

These are easy to break by accident. The README's Architecture section has the
reasoning.

- **Only real applications count.** The funnel reads `jobs` rows with
  `site IN ('email','tracker','ledger')`. Anything that discovers postings
  writes its platform name to `site` instead. Don't widen the filter.
- **No send path.** The Google scope is `gmail.readonly`. Outreach is drafted
  for the person to send. Pull requests that send email, send LinkedIn
  messages, or submit applications on someone's behalf won't be merged.
- **The coach never writes the database.** Snapshot code uses
  `db.connect_readonly()`.
- **Nothing personal in the repo.** No names, schools, employers or emails in
  code, prompts, defaults or tests. Identity comes from the profile through
  `job_bot.candidate`. Test data uses invented people and `.example` domains.
- **Don't guess ATS board tokens.** A company goes into
  `job_bot/watch_registry.py` only after its endpoint has been checked live.
  Wrong tokens return other companies' jobs, or HTTP 200 with nothing.

## Good first contributions

- Skills, role titles and search tracks for another field:
  [`docs/PERSONALIZATION.md`](docs/PERSONALIZATION.md) lists every file that
  still assumes accounting, audit or the DC area.
- A verified company for the watcher registry, or a fetcher for another ATS.
- The open items under "What's next" in the README.

## Reporting a bug

Open an issue with what you did, what you expected, what happened, and the
output of `python -m job_bot doctor`. Remove anything personal from logs and
screenshots first; `python -m job_bot demo` is usually the easiest way to
reproduce a problem without your own data on screen.

Security problems: see [`SECURITY.md`](SECURITY.md).
