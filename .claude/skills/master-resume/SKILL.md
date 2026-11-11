---
name: master-resume
description: Build or update the owner's master résumé, a multi-page LaTeX file holding everything they have ever done, kept in their Overleaf project. Use for "build my master résumé", "add this to my master", "update the master", or when setup reaches the master résumé step.
---

# Master résumé

The master is a superset: every job, project, role and true bullet the owner
has, on as many pages as it takes. Tailored résumés are made by cutting from
it. Nothing goes into a tailored résumé that isn't in the master first.

Read `rules/resume_rules.md` and `rules/overleaf.md` before starting, then
`coach/rules.md` for the owner's settled facts and corrections.

## Build it

1. **Source.** Work from `resume/profile.md`. If it doesn't exist, run the
   profile step of the `setup` skill first.
2. **Draft** `resume/master_resume.tex` from
   `templates/resume/master_resume.tex`, keeping the preamble unchanged.
   - Every entry in the profile gets an entry here.
   - Write every true bullet you can support: five to seven on main roles is
     normal. Variants that stress different sides of the same work (the
     technical side, the client side, the numbers) are useful; tailoring picks
     among them.
   - Each bullet is one line. Lead with a verb that matches what happened.
   - Skills lists only what appears in a bullet, project or course.
3. **Compile and check** as `rules/overleaf.md` describes:
   `python tools/check_resume.py <master.pdf> --master`. Fix under-filled and
   wrapped bullets. Repeated verbs are allowed in the master, but give
   tailoring enough different verbs to choose from.
4. **Review with the owner.** Go through it entry by entry. For each one ask
   what is missing and what is overstated. Anything they can't confirm comes
   out. Record confirmations and removals in `coach/rules.md`.
5. **Overleaf.** If they don't have an account, send them to
   overleaf.com/register (they create it; never type a password for them).
   They make a blank project called "Master Resume". Put the file in as
   `main.tex`, compile, and have them look at the PDF. Save the project link
   in `coach/COACH.md`.

## Keep it current

- New experience, a new number, a finished course: add it to
  `resume/profile.md` and the master in the same session, then sync Overleaf.
- If the owner edits the master in Overleaf themselves, pull it and overwrite
  the local copy before doing anything else. Their edit wins.
- When a tailored résumé needs a bullet the master doesn't have, confirm the
  fact with the owner, add it to the master, then use it.
- When a fact is corrected, fix the master and note in `coach/rules.md` that
  older submitted files still carry the old wording. Don't edit files that
  were already submitted; they are the record of what each employer saw.
