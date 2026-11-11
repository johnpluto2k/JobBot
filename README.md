# Job Bot

A career coach that runs in [Claude Code](https://claude.com/claude-code). You
give it everything you've ever written about yourself. It builds a master
resume, cuts a tailored one-page resume and cover letter for each job you apply
to, keeps your applications in a Google Sheet, and tells you honestly where
your search stands.

## Get started

1. **Download** this project (green **Code** button, **Download ZIP**) and unzip it.
2. **Double-click** `Start Coach - Windows` or `Start Coach - Mac`.
3. **Say** `set me up`.

The full walkthrough, with what to do if something doesn't open, is in
**[SETUP.md](SETUP.md)**. It takes about 20 minutes.

You need a paid Claude plan, a Google account, and Chrome.

## What it does

```
 your documents ──▶ profile ──▶ master resume ──▶ tailored application ──▶ tracker sheet
   documents/       resume/       Overleaf          applications/          Google Sheets
                                                                                │
                                              coach check-ins  ◀────────────────┘
```

1. **Intake.** Drop every resume, cover letter, transcript and project
   write-up you have into `documents`. The coach reads all of it, writes a
   factual profile, and asks about anything that doesn't add up.
2. **Master resume.** A multi-page resume with everything you've ever done,
   kept in your own Overleaf project.
3. **Tailored applications.** Give it a job posting. It picks what fits,
   builds a one-page resume and a cover letter, measures the result, and has a
   second agent review it the way a recruiter would.
4. **Tracking.** When you say you've applied, it adds a row to your Google
   Sheet: company, role, date, status, location, pay, work mode, deadline.
5. **Coaching.** Ask "where are we?" and it reads the sheet, then tells you
   what is time-sensitive, one honest observation, and one thing to do next.

## What's in the folder

| You'll use | |
|---|---|
| `Start Coach - Windows` / `Start Coach - Mac` | Double-click to open your sheet and your coach (as a tab in Orca if you use it, otherwise in its own window) |
| `SETUP.md` | The setup walkthrough |
| `documents/` | Where you put everything you already have |
| `applications/` | Where the coach puts each application, one folder per job |
| `resume/` | Your profile and master resume (created during setup) |
| `coach/` | The coach's notes about you and your search (created during setup) |

| You can ignore | |
|---|---|
| `CLAUDE.md`, `AGENTS.md` | The coach's instructions; Claude reads them automatically |
| `rules/` | How resumes are written, how the coach talks, how the sheet is used |
| `templates/` | The blank tracker, resume layouts and blank coach notes |
| `tools/` | The script that measures your resume, and the launcher's code |
| `examples/` | A finished resume and letter for a fictional student |

Everything in `documents`, `applications`, `resume` and `coach` stays on your
computer and is never uploaded with the project.

## Why the resumes come out well

Every tailored resume has to pass three measured checks
([`rules/resume_rules.md`](rules/resume_rules.md)):

- **Every bullet is one full line**, 92% to 99% of the page width.
- **The same number of bullets per entry on every resume.**
- **The page is filled to the bottom**, with about a quarter inch to spare.

And one rule above all of them: **nothing is invented.** No number, tool,
course or title that can't be traced to your documents or to something you
said. Where you don't match a posting, the coach tells you instead of
papering over it.

See [`examples/`](examples/) for what comes out.

## What it will not do

- **Send or submit anything.** It drafts, and can fill in a form when you ask.
  You press Send and Submit.
- **Guess at your progress.** If it can't read your sheet, it says so.
- **Upload your data.** Your tracker is a sheet in your own Google Drive, and
  your files stay in folders Git ignores.

## Changing how it behaves

Everything the coach does is written in plain English in Markdown files. Tell
the coach what you want different ("always keep my check-ins to three
sentences", "use 4 bullets for my main job") and it records it in
`coach/rules.md`, which overrides the defaults in `rules/`.

## About

This started as one student's job-search tool and was used for about fifty
applications before being opened up. The rules in it are the ones that
survived that search. An earlier version was a web dashboard with a database;
it is still in the git history.

Improvements are welcome, especially for fields other than business and
technology: see [CONTRIBUTING](.github/CONTRIBUTING.md),
[SECURITY](.github/SECURITY.md) and the [changelog](.github/CHANGELOG.md).
MIT licensed; see [LICENSE](LICENSE).
