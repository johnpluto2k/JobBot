# Public-Safe Resume Tailoring Loop Prompt

**Sanitization level:** ECC-compliant (no personal data, company names, or identifying details)

**Use:** Share with colleagues, reference implementations, or portfolio documentation.

---

## Resume Tailoring Loop: Trial-and-Error Iteration Pattern

### Goal
Automate dual-track resume generation, scoring, and human review for job applications where:
1. ✅ Resume passes human recruiter review (formatting, structure, no fabrication)
2. ✅ ATS score ≥ 70 (entry-level acceptable baseline)
3. ✅ Zero violations of resume-track contract

---

## Track Decision Logic

**Determine track from JD keywords:**

- **Track A** (technical emphasis): 3+ mentions of {Python, SQL, analytics, backend, architecture, API, database design, system design}
  - Output: PDF via engineering template (Typst)
  - Section order: Skills → Projects → Experience → Education
  
- **Track B** (business/operations emphasis, default): Everything else (audit, compliance, finance, operations, risk, management)
  - Output: DOCX via business template
  - Section order: Experience → Leadership → Education → Projects → Skills

**Special rule:** Roles that combine technical + business aspects (e.g., "IT Risk", "Financial Systems Audit") default to Track B unless the JD heavily emphasizes technical stack.

---

## Workflow: Automated Tailoring Loop

### Iteration N: Generate → Score → Review → Fix

**Input:** 
- Job description (full text)
- Candidate profile (structured YAML/JSON with experience, projects, education, skills)
- Detected track (A or B)

**Step 1: Generate**
- Template-fill resume from candidate profile
- Reorder sections per track contract
- Select 2–3 most relevant experience bullets + quantify
- Condense or expand projects per track (2 lines max for Track B, 4–5 for Track A)

**Step 2: Score**
- Run ATS engine: detect ATS platform, extract keywords, score coverage
- Report: overall score, keyword hits/gaps, quantification check

**Step 3: Recruiter Review**
- Have a human reviewer check:
  - Section order correctness
  - No fabrication (all bullets trace to source profile)
  - Tense discipline (present for ongoing roles, past for completed)
  - Bullets are specific, quantified, impact-focused
  - No jargon, readable in 10 seconds

**Step 4: Verdict**
- ✅ PASS → Move to output stage
- ❌ FAIL → Extract defects, fix (see Recovery below)

### Recovery: Fix Defects (Max 3 Iterations)

1. Categorize defects:
   - **Kill** (fabrication, wrong section order, contract violations)
   - **Major** (wrong tense, missing metrics, weak bullet wording)
   - **Minor** (readability, comma usage, etc.)

2. Fix in order: Kill → Major → Minor

3. Re-render, re-score, re-review

4. If still failing after 3 attempts: Stop and report profile-JD gap to user

---

## Track Contract Details

### Track A: Technical Resume

**Section order:** Skills → Projects → Experience → Education

| Section | Requirement | Example |
|---------|-------------|---------|
| **Skills** | Technical stack listed first: languages, tools, frameworks | Python, SQL, React, AWS, Tableau |
| **Projects** | 2 featured projects with 4–5 bullets each; emphasize architecture + impact | "Built a data pipeline with Python + SQL that processes 1M records/day; improved query latency by 40%" |
| **Experience** | 2–3 bullets per role; technical outcomes emphasized | "Owned analytics dashboard redesign, reducing query time by 30%" |
| **Education** | Degree + 15+ relevant courses (data, CS, math, business) | BS Computer Science; Coursework: Data Structures, Machine Learning, Databases, Statistics |

**Tone:** Technical depth, portfolio-focused, architecture language

### Track B: Business Resume

**Section order:** Experience → Leadership → Education → Projects → Skills

| Section | Requirement | Example |
|---------|-------------|---------|
| **Experience** | 3+ roles with 3 bullets each; quantified business impact | "Managed $500K budget, identified $50K in cost savings via process optimization" |
| **Leadership** | 2 entries; initiative + governance emphasis | "Led compliance audit that identified 15 control gaps; resolved 12 within 90 days" |
| **Education** | Degree + 10–12 courses (accounting, finance, operations, management) | BS Accounting, BS Business Analytics; Coursework: Financial Reporting, Risk Management, Systems Design |
| **Projects** | Minimal (2 lines max per project); frame as business initiative not tech | "Designed inventory system reducing waste by 15%" (not: "Built Django app with PostgreSQL") |

**Tone:** Experience-first, leadership-focused, business outcome language

---

## ATS Baseline & Acceptance Criteria

| Metric | Target | Acceptable | Action |
|--------|--------|-----------|--------|
| **ATS Score** | 75–90 | ≥70 | If <70 after 3 iterations, stop (profile gap) |
| **Recruiter Review** | PASS | PASS | Iterate until PASS; cap at 3 attempts |
| **Contract Compliance** | 100% | 100% | Must not deviate from track contract |

**Philosophy:** Human recruiter judgment > ATS bot. If recruiter rejects but ATS >85, quality wins.

---

## Deliverables

Per job application:
```
applications/{employer}_{role}/
  ├── resume.{docx|pdf}
  ├── resume.pdf (copy for portals)
  ├── cover_letter.docx + .txt
  ├── checklist.md (extra materials)
  ├── jd_snapshot.txt
  └── tailoring_log.txt (audit trail)
```

**Tailoring log entry example:**
```
---
date: 2026-07-09
jd: "Senior Data Analyst at TechCorp"
track: A (technical)
iteration_1:
  ats_score: 68
  recruiter: FAIL — wrong section order, projects too technical
iteration_2:
  ats_score: 72
  recruiter: PASS — section order fixed, projects reframed as impact-first
---
```

---

## Key Principles

1. **Never fabricate:** All bullets must trace to source profile (resume, transcript, projects, cover letters)
2. **Respect the contract:** Track A ≠ Track B; violating section order signals careless work
3. **Quantify ruthlessly:** "improved accuracy by 18%" > "improved accuracy"
4. **Stop when gap is real:** If JD requires "5+ years AWS" and candidate has 0, 3 iterations won't fix it
5. **Recruiter review is line 1 QA:** If a human reviewer catches issues, they're real (don't argue with recruiter feedback)

---

## Implementation Checklist

- [ ] Profile data is complete, accurate, and sourced (no placeholder entries)
- [ ] JD is parsed for keywords, ATS platform, required vs. preferred skills
- [ ] Track is correctly assigned (audit track keyword rules implemented)
- [ ] Templates exist and are versioned per track
- [ ] ATS engine is calibrated (baseline scoring known)
- [ ] Recruiter review process is repeatable (checklists, consistency)
- [ ] Defect recovery is automated (common fixes encoded)
- [ ] Audit trail is logged (every iteration recorded)
- [ ] Output paths are consistent and versioned

---

## Example: Loop in Action

```
INPUT: JD for "Data Analyst" role + candidate profile

TRACK DETECTION: 
  Keywords found: Python (yes), SQL (yes), analytics (yes), dashboard (yes)
  → Track A (technical)

ITERATION 1:
  Generate: Section order = Skills → Projects → Experience
  ATS Score: 68/100 (Python ✓, SQL ✓, Tableau ✗, missing domain keywords)
  Recruiter: FAIL — "Projects section lacks architecture depth, experience bullets too generic"
  
ITERATION 2:
  Fix: Expand project bullets with system design detail; reword experience for technical outcomes
  Render: Regenerate resume PDF
  ATS Score: 74/100 (architecture keywords added, Tableau still missing)
  Recruiter: PASS — "Strong project portfolio, clear technical progression, no fabrication"
  
OUTPUT: 
  Deliver resume + cover letter + checklist
  Log: 2 iterations, final ATS 74, recruiter approved
```

---

## Caveats & Failure Modes

- ❌ **Profile gap is real:** If candidate lacks required certification or 5+ years of role-specific experience, loop won't close (ATS will stay <70). Escalate to user.
- ❌ **Recruiter is stuck on fabrication:** If reviewer says "this bullet is false," trust the reviewer. Either source the bullet from profile or remove it.
- ❌ **ATS vs. Human conflict:** If ATS is 88 but recruiter rejects (or vice versa), prioritize human judgment. Iterate on human feedback.

---

**Version:** 1.0 (July 2026)
**Source:** Job application system trial-and-error loop, proven on dual-track tailoring
