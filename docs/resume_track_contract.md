# Resume Track Contract

This document defines how John's resume splits into two **complementary but distinct** business and tech tracks. Both are true profiles of John; they differ in emphasis and content hierarchy.

## Track Definitions

### Business Track (Default)
**Target roles:** IT Audit, Technology Risk, IT Risk/Compliance, Big 4 Audit, Internal Audit, FinTech Risk/Operations, Accounting, Finance Operations

**Content hierarchy (top to bottom):**
1. **Professional Experience** (work history, 3+ roles with quantified impact)
   - Leasing Consultant @ Scion Group (800+ tenants, 18% data accuracy gain)
   - UMD Teaching Assistant (30+ students, 15% satisfaction lift)
   - Manager @ Kim's Grill (audit readiness, $380K budget, $25K cost savings)

2. **Leadership** (professional/academic leadership, 2–3 entries)
   - TerpTax member (30+ tax returns, 20% error reduction)
   - Pi Sigma Epsilon: KPMG Case Competition semifinalist (80% energy savings projection)

3. **Education** (degree, GPA, relevant coursework highlights)
   - UMD: BS Accounting + BS Information Science, 3.51 GPA, May 2027
   - 10–12 highlight coursework bullets (accounting, audit, systems, finance)

4. **Projects** (short, 2 lines max per project; framed as initiative/impact)
   - Keep Pathway brief: "Designed a resume tailoring + ATS scoring system…"
   - Keep PersonalFinanceOS brief: "Built a fintech dashboard with Plaid integration…"
   - (Tech details de-emphasized; business outcome emphasized)

5. **Technical Skills** (compact section: Python, SQL, Excel, Tableau, R)

**VMH Template Requirements:**
- DOCX format (`.docx`, not PDF)
- Strict one-page, 10–11pt body font
- Exact section order per above
- No projects section header if <2 items

**Audience Signal:** Recruiter is hiring for control, compliance, finance, or IT risk—values audit trail, precision, experience depth.

---

### Tech Track
**Target roles:** Data & Analytics, Data Engineer, Analytics Engineer, Software Engineer (entry), IT Systems Architecture, FinTech Engineering

**Content hierarchy (top to bottom):**
1. **Skills** (technical stack first: Python, SQL, Tableau, R, Node.js, React, FastAPI, SQLite)
   - Reorganize: technical skills → databases/tools → soft skills

2. **Projects** (prominent, 4+ bullets per project; stack + architecture emphasized)
   - Pathway: "Built a 60+ module Python system with Claude API, React, FastAPI…"
   - PersonalFinanceOS: "Built a zero-dependency Node.js backend, SQLite, Plaid adapter…"
   - Pantry Plate: as originally formatted (full stack)

3. **Education** (degree, GPA, **expanded coursework**)
   - Same school/degree, but highlight: OOP I, OOP for Info Science, Database Design, Intro to Programming, Python/Web focus

4. **Professional Experience** (compressed; 2 bullets max per role, focus on technical outcomes)
   - Scion: "Used CRM reporting…to improve data accuracy by 18%"
   - UMD TA: "Created grading analytics dashboards" (tech emphasis)
   - Kim's: "Designed inventory tracking system with financial controls"

5. **Leadership** (optional, minimal; max 1–2 lines if included)

**RenderCV/Typst Template Requirements:**
- PDF output via RenderCV engineering theme (Typst)
- One-page target, 9–10pt body
- Code block styling for tech stack
- Section order as above

**Audience Signal:** Recruiter is hiring for execution—values architecture, system design, languages, hands-on depth.

---

## Track Assignment Rules

**Default:** Business track (VMH/DOCX).

**Switch to Tech if JD contains 3+ of these keywords:**
- Python, SQL, React, Node.js, data engineer, analytics engineer, database, API, backend, architecture, full-stack, TypeScript, JavaScript, system design, ETL

**Ambiguous:** IT Audit / Tech Risk jobs stay **business** by default (audit-firm culture values compliance/controls over coding); move to tech only if the JD emphasizes "systems architecture" or "technical infrastructure."

**Log:** Every tailoring run should note which track was chosen and why (keyword match count, ambiguity resolution).

---

## Acceptance Criteria

**Per track, the rendered resume must:**
1. ✅ Pass `recruiter-reviewer` (formatting, section order, no fabrication)
2. ✅ ATS score ≥ 85 (from `job_bot/ats_engine.py`)
3. ✅ Zero contract violations (wrong section order, misplaced projects, etc.)
4. ✅ Exactly one page (within 10pt–11pt range for business; 9pt–10pt for tech)

A resume that scores 88 ATS but fails recruiter review = **reject**. One that passes human review but scores 80 ATS = **reject**. Both gates must pass.

---

## Implementation Notes

- `template_select.py:renderer_for_field()` already routes based on `TECH_FIELDS` — update the routing logic to align with track assignment rules above.
- `tailor.py` should log track choice + reasoning to stdout before rendering.
- `resume_models.py` may need a `TrackConfig` model to hold section-ordering rules per track.
- The `recruiter-reviewer` agent will read the rendered `.docx` or `.pdf` and validate section order against this contract.
