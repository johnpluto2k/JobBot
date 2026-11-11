# Job Bot: instructions for coding agents other than Claude Code

This project is a career coach written as instructions, rules and templates.
The full operating notes are in [`CLAUDE.md`](CLAUDE.md); read that file first
and follow it. This file exists so tools that look for `AGENTS.md` find the
same rules.

The short version:

- The person running the project is **the owner**. Their identity and history
  come from their private files (`coach/`, `resume/`, `documents/`), never from
  tracked files.
- The process is intake, master résumé, tailored applications, tracking in
  the owner's Google Sheet, and coaching from that sheet.
- Rules live in `rules/`. The owner's `coach/rules.md` overrides them.
- **Never send a message or submit an application.** Draft only.
- **Never invent a fact** about the owner.
- **Never put personal data in a tracked file.** `documents/`, `resume/`,
  `applications/` and `coach/` are gitignored.
- The skills in `.claude/skills/` and helpers in `.claude/agents/` are plain
  Markdown procedures. An agent that can't load them as skills can still read
  and follow them.
- The tracker sheet is read through a Google Drive integration and written
  through browser control, as `rules/tracker_sheet.md` describes. Without
  those, hand the owner the row to paste.
- For changes to the project itself: run `python -m pytest` (tests are in `tools/tests/`), use fictional
  people in examples and tests, and commit or push only when asked.
