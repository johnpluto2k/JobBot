---
name: setup
description: First-run onboarding for a new owner. Checks the required tools, creates their private folders and tracker sheet, reads their documents into a profile, and interviews them for targets. Use when coach/COACH.md does not exist, or when the owner says "set me up", "get started" or "redo setup".
---

# Setup

Walk a new owner from an empty folder to a working coach. Go one step at a
time, show what each step produced, and wait when a step needs them (a sign-in,
a click, a file to drop in). Use plain language; assume they have never used a
terminal before today.

Never commit or print the contents of `documents/`, `resume/`, `applications/`
or `coach/`. Never send, submit or post anything.

If `coach/COACH.md` already exists, this is a redo: ask which step they want
and don't overwrite existing files without asking.

## Step 1. Check the tools

Check each and report a short table of what is ready and what is missing:

- **Google Drive connector.** Try a harmless Drive call (list recent files).
  If no Drive tools are available, tell them to add it at
  claude.ai/customize/connectors, then run `/mcp` here.
- **Claude in Chrome.** Ask for the browser tab context. If the tools are
  missing, point at SETUP.md step 2 (the extension link, then `/chrome`).
- **Python.** Run `python --version` (or `python3`, or `py` on Windows). Then
  `python -m pip install -r tools/requirements.txt` if `import pdfminer` fails.
- **Gmail connector** (optional). Note whether it is there.

Missing Drive or Chrome doesn't stop setup. Say what each missing tool will
cost them (no automatic sheet reads; rows handed over to paste) and continue.

## Step 2. Private folders

`documents/` and `applications/` ship with the project. Create `resume/` and
`coach/` with `coach/firms/` and `coach/log/`. Copy `templates/coach/COACH.md`, `STATE.md` and `rules.md`
into `coach/`. Run `git status` and confirm none of the new files show as untracked; if
any does, stop and fix `.gitignore` first.

## Step 3. The tracker sheet

Create their own copy. Upload `templates/tracker_template.xlsx` through the
Drive connector with the title "Job Tracker", letting Drive convert it to a
Google Sheet. Upload it by file reference; don't paste the file's contents.

If Drive isn't connected, ask them to do it by hand: open sheets.new in the
browser, File, Import, Upload, choose `templates/tracker_template.xlsx`,
"Replace spreadsheet". Then ask for the link.

Write the link and file id to `coach/tracker.md`. Open the sheet in a new
browser tab so they can see it. Read `rules/tracker_sheet.md` before touching
it. Leave the Tracks list for step 6.

## Step 4. Their documents

Ask them to put everything they have into `documents/`: every résumé version,
cover letters, transcripts, project write-ups, performance reviews, award
letters, a LinkedIn profile PDF and connections export if they have one. More
is better; they don't need to tidy it. Wait until they say it is in.

Then read all of it. For large folders, list the files first and read the
career-relevant ones (résumés, letters, transcripts, project documents) in
full; skim the rest. PDFs and Word files can be read directly.

## Step 5. The profile

Write `resume/profile.md`: the factual record everything else is cut from.

- Contact line, links
- Education: school, degrees, dates, GPA, completed courses (from the
  transcript, with in-progress courses marked as in progress)
- Every job, internship, project, leadership role, competition, award and
  certification, each with dates, location, and every true detail found:
  what they did, tools, numbers
- Skills, each with where it was used
- A **Needs confirmation** section: every place two documents disagree, every
  number that appears only once, every title or date you are unsure of

Cite the source file for anything that might be questioned. Do not round up,
merge two roles, or fill a gap with a guess.

Then go through **Needs confirmation** with the owner, a few questions at a
time. Record each answer in the profile and each settled fact or rejected
claim in `coach/rules.md`.

## Step 6. Targets

Interview them, one question at a time:

1. What kinds of roles are you going for? (These become the Tracks: two to
   eight short labels, such as Consulting, Data, Software.)
2. Internship, full-time, or both? Which graduation or start date goes on
   applications?
3. Where do you want to work, and how do you feel about remote?
4. Which employers are you most interested in?
5. How many applications a week is realistic for you?
6. Anything the coach must respect? (Visa timing, relocation limits, a job
   you can't mention, things you don't want on a résumé.)

Write the answers into `coach/COACH.md`. Enter the Tracks in the sheet's Setup
tab, cells A2 down, through the browser (or ask them to type them in), and
check the By Track box on the Tracker tab picked them up.

## Step 7. Master résumé

Run the `master-resume` skill. This is the longest step; tell them so.

## Step 8. Hand off

- Put a first START HERE agenda (two or three items) in `coach/STATE.md` and a
  dated line in `coach/log/<YYYY-MM>.md`.
- Run `git status` once more and confirm nothing private is tracked.
- Tell them the three things they will say most:
  - "Tailor an application for this posting: <link>"
  - "I submitted the <company> one"
  - "Where are we?"
- Ask which they want to do first.
