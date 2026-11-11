# Contributing

Job Bot is a career coach written mostly in Markdown: rules, skills and
templates that Claude Code follows. It started as one person's job-search tool
and is still shaped by that search, so improvements that make it work for
other fields and other kinds of applicant are especially welcome.

## Get a working copy

```
git clone https://github.com/johnpluto2k/JobBot.git
cd JobBot
python -m pip install -r tools/requirements.txt
python -m pytest
```

To try the coach itself, follow [SETUP.md](../SETUP.md) with a throwaway Google
Sheet and a few sample documents.

## What lives where

| Change | File |
|---|---|
| How résumés and letters are written and checked | `rules/resume_rules.md` |
| Coaching tone and memory | `rules/coaching_rules.md` |
| Sheet columns and how the coach writes rows | `tools/build_tracker_template.py`, `rules/tracker_sheet.md` |
| A step of onboarding, tailoring or check-ins | `.claude/skills/<name>/SKILL.md` |
| A helper agent | `.claude/agents/<name>.md` |
| The PDF checks | `tools/check_resume.py`, with a test in `tools/tests/` |
| The launchers | `Start Coach - Mac.command`, `tools/start.ps1` (both have a dry-run mode) |
| LaTeX layout | `templates/resume/` and the compiled copies in `examples/` |

If you change the tracker layout, rebuild the workbook
(`pip install openpyxl`, then `python tools/build_tracker_template.py`) and
update `rules/tracker_sheet.md` in the same pull request. The coach's
instructions depend on the header being in row 15.

If you change a LaTeX template, recompile the example and make sure
`python tools/check_resume.py examples/sam_rivera_resume.pdf --tex examples/sam_rivera_resume.tex`
still passes.

## Rules the project depends on

- **No send path.** The coach drafts; the person sends and submits. Changes
  that send email or messages, or submit applications, won't be merged.
- **Nothing is invented.** Don't add a rule or prompt that encourages padding
  a résumé to match keywords.
- **Nothing personal in the repository.** No real names, schools, employers or
  email addresses in rules, skills, templates, examples or tests. Examples use
  the fictional Sam Rivera and `.example` domains.
- **Write for someone who has never used a terminal.** Instructions the coach
  gives a user should be plain and specific.

## Before you open a pull request

- `python -m pytest` passes.
- One topic per pull request, and say how you tried it.
- For a rule or skill change, describe the conversation you tested it with and
  what the coach did differently.

## Reporting a problem

Open an issue with what you asked the coach, what you expected and what it
did. Remove anything personal first. Security problems: see
[SECURITY.md](SECURITY.md).
