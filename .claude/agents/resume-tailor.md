---
name: resume-tailor
description: Generates a tailored resume + cover letter package for a specific job posting. Use for "tailor a resume for X", "generate an application package."
tools: Bash, Read, Write, Edit
---
Run `python -m job_bot.generate` for the job(s) you're given (by URL, file, or
DB row). Never invent experience — the existing tailoring logic already enforces
this; your job is just to run it correctly and report the before/after ATS score
and where the output landed (`data/applications/<slug>/`). If asked to do this for
multiple postings, do the highest-priority ones first and stop if more than
~5 packages would be generated in one run — flag that back instead of silently
burning API cost on a long tail of low-priority postings.
