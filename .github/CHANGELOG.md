# Changelog

Newest first.

## 2026-11-11: Rebuilt around the coach and a Google Sheet

The project is now a Claude Code career coach, not a web app.

- **Removed:** the FastAPI server, the React dashboard, Google sign-in, the
  Gmail sync, the SQLite database, the company posting watcher, the Streamlit
  tools and the demo mode. All of it is still in the git history.
- **Tracking is a Google Sheet.** `templates/tracker_template.xlsx` becomes the
  user's own sheet during setup: one row per application (company, position,
  date, status, details, portal, cold apply, location, pay, work mode, grad
  date, deadline, track), summary boxes that count themselves, and an Outreach
  tab. The coach reads it through the Google Drive connector and adds rows
  through Claude in Chrome.
- **A four-stage process:** intake from `documents/`, a multi-page master
  résumé in Overleaf, tailored one-page applications, tracking and check-ins.
  Each stage is a skill in `.claude/skills/`.
- **The résumé method is written down** in `rules/resume_rules.md` and enforced
  by `tools/check_resume.py`: one full line per bullet, fixed bullet counts,
  page filled to the bottom, no repeated verbs, nothing invented.
- **Flat private folders:** `documents/`, `resume/`, `applications/`, `coach/`
  at the top of the project. An application is `applications/<Company>_<Role>/`
  with the PDFs to upload on top.
- **No API key, no Google Cloud project, no Node.** Requirements are Claude
  Code, the Google Drive connector, the Claude in Chrome extension and Python.
- **One setup guide** for Mac and Windows: `SETUP.md`. Three steps before the
  coach takes over.
- **Launchers:** double-click `Start Coach - Windows` or `Start Coach - Mac`.
  They check Claude Code and Python are installed (asking before installing),
  open the two connect pages on a first run, then open the sheet and the coach.
  With the Orca app installed and the folder open in it, the coach opens as a
  tab there; otherwise it opens in the launcher's own window.

## 2026-11-10: Last dashboard version

Last version of the dashboard app: fictional demo, sign-in-free local mode, a
single `serve / demo / doctor` entry point, packaging with optional extras,
MIT license, contributing and security files.

## Before November 2026

The dashboard era, from July to October 2026: profile extraction, ATS scoring,
tailored generation, a company-first tracker, Gmail sync, a posting watcher
and the first version of the coach. The full history is in the git log.
