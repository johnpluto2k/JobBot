# Résumé and cover letter rules

These rules came out of a real search: roughly fifty tailored applications to
consulting, audit, analyst and software roles, and the mistakes caught along the
way. They apply to every résumé and letter the coach writes. The owner's own
decisions in `coach/rules.md` override them.

## 1. Truth comes first

- **Never invent anything.** That covers metrics, tools, courses,
  certifications, responsibilities, events, and a teammate's work presented as
  the owner's. Not even to match a keyword.
- If a claim can't be traced to `documents/` or to something the owner said,
  it stays off the page. "I think it was about 20%" is not a number. Ask.
- A gap is described as something the owner wants to learn, never as something
  they have done.
- **One graduation or start date per company.** Recruiters see every
  application a person sends them. Before a submission, check that the date
  fits the role type (internship or full-time).
- List only completed courses, never scheduled ones.
- Every tool in Skills shows up somewhere else on the same page: a bullet, a
  project or a course.
- Record each fact the owner confirms, and each claim they reject, in
  `coach/rules.md` so it is never asked twice or reused by mistake.

## 2. Wording the entries

- Use titles the owner can defend. An early engineer at a startup puts
  "founding" in a bullet, not in the title.
- Use verbs that match what happened: Built, Developed, Implemented, Shipped.
  Designed and Architected only when the owner owned the design.
- Be exact about numbers: users or paying customers, merged or still on a
  branch, "88 companies" not "90+".
- Read each phrase as a skeptical recruiter would. "Agents that automate
  résumé tailoring" can read as "a bot wrote this résumé."
- Decide each optional entry (an older job, a side project) per employer. One
  company's choice is not copied onto every résumé.

## 3. Layout

- **One page** for a tailored résumé. The master can run to several.
- Order: Education, Experience, Leadership, Projects, Skills. For technical,
  data and analyst roles, Projects goes above Leadership.
- Packed page: 0.4in side margins and small gaps between entries, using the
  preamble in `templates/resume/resume.tex`. Never stack negative `\vspace` to
  squeeze more in.
- Degrees on one line where possible, with the graduation date on the
  university line.
- **No action verb is repeated anywhere on the page.**
- No Interests row unless the posting makes it relevant.

## 4. Three checks every tailored résumé must pass

Run `python tools/check_resume.py <resume.pdf> --tex <resume.tex>` after every
compile. It measures the PDF; do not judge these by eye or by asking a model
for a character count.

1. **Every bullet is one full line, 92% to 99% of the width.** A bullet that
   wraps with three words on the second line wastes a line. Exactly 100% can
   push trailing space onto an invisible extra line in some templates. To fit a
   bullet, write a few versions of slightly different length and measure each.
2. **The same bullet counts on every résumé.** Defaults: 3 per job, 3 per
   project, 2 per leadership or case-competition entry. The owner can set
   their own in `resume/bullet_counts.json` (for example 5 for their main
   job). To fill or free space, add or remove a **whole entry**. Never stack
   extra bullets on one.
3. **The page is filled to the bottom:** 0.20in to 0.35in of blank space below
   the last line. If something is cut, the space is refilled with true content
   (another verified bullet's entry, or a project). Never loosen spacing to
   fake it.

A package is not "ready" until the checker passes and you have looked at the
rendered PDF.

## 5. Text formatting

- Plain ASCII: "resume" and "cafe", no accents. Accented characters extract as
  a letter plus a combining mark, which résumé parsers can mangle.
- A heading and its descriptor are separated by a spaced en dash
  (`Project -- What it is` in LaTeX), never an em dash. Dates use plain
  hyphens.
- Spell out acronyms a recruiter may not know and keep the acronym in
  parentheses: "customer relationship management (CRM)". Leave common ones
  alone (AI, SQL, GPA, SaaS).
- Tie short related items together (`R,~SQL`) so they can't break across lines.

## 6. Cover letters

- Write one only when the posting asks for it or the owner wants it.
- **About 5 bullets of roughly 2 lines each**, verb first, built from the
  strongest true examples for this posting. One-liners read as thin;
  paragraphs disguised as bullets are too long.
- Structure: why this role plus the owner's background in one opener, a
  first-person paragraph on the most relevant experience, the bullets, one
  coursework line, a short close.
- One page at 1in margins, with 0.9in to 1.3in blank at the bottom and no
  one-word last line. Check with `python tools/check_resume.py <letter.pdf> --letter`.
- Don't repeat what the application form already collects: referral name,
  citizenship, clearance, home address.
- **It must not sound like AI.** No aphorisms, no colon-reveal sentences, no
  stock phrases, no buzzwords lifted from the posting. Real experiences, told
  plainly.

## 7. Process

- The **master résumé** holds every true bullet the owner has. Tailoring cuts
  from it. New content goes into the master first, after the owner confirms
  it, and only then onto a tailored page.
- Don't chase an ATS score. List the posting's key terms, mark which ones the
  page honestly covers, and report the real gaps.
- Build, compile, look at the PDF, run the checker. Then one independent
  review (the `recruiter-reviewer` agent), targeted fixes, and stop. No
  cosmetic rewrite loops.
- File names: `Last_First_Company_Role_Resume.pdf` and
  `Last_First_Company_Role_CoverLetter.pdf`.
- Each application gets its own folder, `applications/<Company>_<Role>/`, with
  the PDFs to upload and the posting on top and LaTeX sources in `source/`.
  Save the posting text the day you fetch it; postings disappear.
- When the owner says they submitted, add the row to the tracker sheet.
- **The owner reads the final PDF and clicks Submit.**
