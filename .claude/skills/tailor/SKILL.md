---
name: tailor
description: Build a tailored application for one job posting, a one-page résumé cut from the master and a cover letter if needed, checked and reviewed, then log it in the tracker sheet once the owner submits. Use for "tailor an application for this posting", "make a résumé for X", "apply to this", or when the owner pastes a job link or description.
---

# Tailor an application

Read `rules/resume_rules.md`, `rules/overleaf.md`, `coach/rules.md`, and
`coach/firms/<firm>.md` if one exists. Follow them over anything below.

## 1. The posting

- Open the link with the browser tools (many job sites return an empty page to
  a plain fetch) and read the whole posting. If the owner pasted text, use it.
- Create `applications/<Company>_<Role>/` (hyphens inside a part, underscore
  between parts, add the requisition number or city when the same title is
  posted more than once). Save the posting as `posting.md` with the link,
  requisition number, location, pay, work mode, deadline and the date fetched.
- Check the tracker sheet for earlier applications to this employer. Use the
  same graduation or start date as before. If the role type and the date
  clash (a full-time role against an internship date), stop and ask.
- Tell the owner in two or three lines what the role is, the honest fit, and
  the real gaps. If it is clearly a poor fit, say so before building anything.

## 2. Plan the page

- List the posting's key terms. Mark each one covered by the master, or a gap.
  Gaps are reported, never papered over.
- Choose which entries from `resume/master_resume.tex` go on the page and
  which bullets for each, using the fixed bullet counts. Choose the section
  order. Ask about any optional entry the owner hasn't ruled on for this
  employer.

## 3. Build

- Start from the closest earlier tailored file if one fits (same track),
  otherwise from `templates/resume/resume.tex`. Save as
  `applications/<Company>_<Role>/source/resume.tex`. Earlier files carry
  employer-specific choices; don't inherit a date or an entry by accident.
- Cut and reorder from the master. Rephrase a bullet to fit the line or to
  avoid a repeated verb; never change its facts.
- Compile, run `python tools/check_resume.py <pdf> --tex <tex>`, look at the
  page, fix, repeat until it passes.
- Cover letter only if the posting asks or the owner wants one: start from
  `templates/resume/cover_letter.tex`, save as `source/cover_letter.tex`,
  check with `--letter`.
- Put the upload PDFs at the top of the application folder as
  `Last_First_Company_Role_Resume.pdf` and `..._CoverLetter.pdf`.

To build several applications at once, hand each to the `resume-tailor` agent,
about two at a time, and check the files on disk when they finish.

## 4. Review once

Run the `recruiter-reviewer` agent on the finished PDFs and the posting. Fix
the material defects it finds, recompile, re-run the checker. One review, then
stop.

## 5. Hand over

Give the owner: the folder, the checker result, the gaps you could not close,
and anything they need to decide. They read the PDF. If the form has questions
(salary expectation, start date, "why this company"), draft answers from their
facts for them to edit.

You may fill in a web form if they ask, field by field, from their profile.
They review it, tick any acknowledgements, and press Submit themselves.

## 6. After they submit

Only when the owner says it is submitted:

- Add the row to the tracker sheet as `rules/tracker_sheet.md` describes and
  read it back.
- Note anything worth remembering in `coach/firms/<firm>.md` (portal quirks,
  application limits, who referred them) and add a log line.

If they decide not to apply, move the folder to `applications/_dropped/`.
