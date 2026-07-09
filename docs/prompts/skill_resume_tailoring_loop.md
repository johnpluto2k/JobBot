# Skill: Resume Tailoring Loop (Trial-and-Error Iteration)

**Purpose:** Automate the dual-track resume tailoring, scoring, and recruiter review loop for repeatable, high-quality application packages.

**Trigger:** When user requests `tailor a resume for [job description]` or similar.

**Contract:** Input a job description (JD); output a PASS-grade tailored resume + cover letter + checklist where:
1. ✅ Recruiter-reviewer returns PASS (formatting, section order, no fabrication)
2. ✅ ATS score ≥ 70 (realistic baseline for entry-level roles)
3. ✅ Zero contract violations (business vs tech track rules followed)

---

## Workflow (Fully Automated Loop)

### Step 1: Detect Track
Parse JD for keyword density:
- **Tech track** if JD has 3+ of: `{Python, SQL, React, Node.js, data engineer, analytics, database, API, backend, architecture, full-stack, TypeScript, system design, ETL}`
- **Business track** (default): IT Audit, Risk, Compliance, Finance, Accounting roles

Special case: **IT Audit / Tech Risk** stays business track by default (audit-firm culture > SWE culture).

### Step 2: Generate Tailored Resume
Use `resume-tailor` subagent:
- Input: JD text, detected track (business or tech), master_profile.json
- Output: Tailored DOCX (business) or PDF (tech) via appropriate renderer
- Never fabricate: all bullets must trace to master profile

**Acceptance:** ATS score ≥ 70 (target; lower is entry-level leeway)

### Step 3: Recruiter Review (Iteration Loop)
Use `recruiter-reviewer` subagent:
- Input: rendered resume file + JD + track
- Checks:
  1. Section order matches track contract
  2. No fabrication (all bullets trace to profile)
  3. Tense discipline (current roles = present, past = past)
  4. Bullet quantification (numbers where possible)
  5. Human readability (would recruiter keep reading past 10s?)

- Output: VERDICT (PASS | FAIL) + defect list OR approval summary

**If PASS:** Move to Step 4
**If FAIL:** Fix defects (see Loop Recovery below)

### Step 4: Generate Cover Letter & Checklist
Use `resume-tailor` subagent to generate:
- Tailored cover letter mirroring JD language + profile strengths
- Application checklist (extra materials, portal quirks, etc.)

### Step 5: Deliver Package
Output to `data/applications/{company}_{role}/`:
- `resume.docx` or `resume.pdf`
- `cover_letter.docx` + `.txt`
- `checklist.md`
- `jd_snapshot.txt` (JD copy for reference)

---

## Loop Recovery (If Recruiter Returns FAIL)

1. **Extract defects** from recruiter verdict
2. **Fix in priority order:**
   - Kill defects (fabrication, wrong section order) = manual edit + re-render
   - Major defects (tense, missing metrics) = trace to master profile + regenerate
   - Minor defects (wording, readability) = reword in bullets
3. **Re-render** via `tailor.py` with corrected bullets
4. **Re-submit** to recruiter-reviewer
5. **Iterate** (max 3 attempts; if still failing after 3, stop and report to user)

---

## Track Contract (Business vs Tech)

### Business Track (DOCX, VMH Template)
**Order:** Experience → Leadership → Education → Projects → Skills

- **Experience:** 3+ roles, 3 bullets each, quantified impact
- **Leadership:** 2 entries, impact-focused
- **Education:** Degree, GPA, 10-12 relevant courses (emphasize audit/accounting/systems)
- **Projects:** 2 lines MAX per project; frame as initiative/impact, not tech stack
- **Skills:** Compact list (Excel, SQL, Tableau, R, Python, etc.)

**Audience:** Recruiter for audit, risk, compliance, finance roles — values experience depth + credentials.

### Tech Track (PDF, RenderCV/Typst Engineering Theme)
**Order:** Skills → Projects → Experience → Leadership → Education

- **Skills:** Python, R, SQL, Tableau, technical stack (front-loaded)
- **Projects:** 2 featured, 4 bullets each; stack + architecture + impact
- **Experience:** 2 bullets max per role; emphasize technical outcomes
- **Leadership:** 1 entry if included; kept brief
- **Education:** Degree + expanded coursework (16 courses, data/tech/business mix)

**Audience:** Recruiter for data/analytics/SWE roles — values technical depth + portfolio.

---

## ATS Baseline & Acceptance

- **Target ATS score:** 70–85 (70 = solid entry-level, 85 = excellent match)
- **Never push past 85 chasing:** If ATS >85 but recruiter rejects on quality, quality wins (human recruiter > ATS bot)
- **If stuck <70 after 3 iterations:** Profile-JD gap is real (missing certs/experience). Stop and report to user.

---

## One-Line Prompt

```
Tailor a resume for [JD text]. Track: [business|tech]. Master profile: [path]. 
Loop until recruiter PASS + ATS ≥70. Never fabricate. Output to data/applications/.
```

---

## Example: Output Structure

```
data/applications/deloitte_it-audit-analyst-2026/
  ├── resume.docx (or .pdf)
  ├── resume.pdf (for portals that need PDF)
  ├── cover_letter.docx
  ├── cover_letter.txt (plain text for email)
  ├── checklist.md
  ├── jd_snapshot.txt (original JD for ref)
  └── tailoring_log.txt (which track, ATS scores, recruiter verdicts)
```

---

## Implementation Notes

- `resume-tailor` subagent handles all rendering via `tailor.py`, `render_docx.py`, `render_rendercv.py`
- `recruiter-reviewer` subagent handles all human-eye review
- `ats_engine.py` scores after each render
- Defect fixes are pushed back to master_profile.json ONLY if they reveal missing profile data (never rewrite history)
- Loop logs all iterations to `tailoring_log.txt` for audit trail

---

## Caveats

- **No magic:** If a JD requires "5+ years AWS SysOps" and John has none, no amount of wording fixes the gap. Stop loop after 2–3 iterations and report the real gap to user.
- **Recruiter-reviewer is truthful:** If it says "fabrication detected," investigate immediately — fabrication kills applications.
- **ATS scores are directional, not gospel:** An 88 is better than a 72, but both can land interviews if the human recruiter likes the profile.
