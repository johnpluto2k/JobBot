# Super Prompt — Resume Overhaul + Search-Filter Fix (agent trial-and-error)

Paste this whole prompt into a Claude Code session opened in `C:\ClaudeProjects\Job Bot`.

---

You are the **conductor** for an overhaul of two Job Bot subsystems: résumé tailoring and job-search filtering. Work through the phases in order. Delegate to the existing subagents (`resume-tailor`, `job-scout`, `recruiter-reviewer`, plus `code-reviewer` / `tdd-guide` from the parent `.claude/agents` if useful) — delegation is one level deep, subagents never call subagents. **Every step must return evidence** (scores, diffs, file paths, test output). "Done" with no evidence gets re-run. Iterate each loop until its acceptance criteria pass or 5 attempts are exhausted — then stop and report what's blocking instead of shipping something half-right.

Ground rules:

- Work on a git branch (`overhaul/resume-and-filter`). Commit after each passing phase.
- Never destructively modify `data/job_bot.db`; back it up to `data/backups/` first.
- John's historically submitted resumes in `documents/Professional Development/Resumes/` are the **ground truth for voice and format** of the business track. Never invent employment history, dates, GPAs, or metrics — every new bullet must trace to something real in this repo or `data/master_profile.json`.
- Use the installed skills where they apply: **docx** for reading/writing the VMH business template, **pdf** for output checks, **xlsx** if you need `inputs/Internship & Job Tracker.xlsx`, **skill-creator** and **hermes-imports** in Phase 5.

## Phase 1 — Add the two projects to the profile

Job Bot and PersonalFinanceOS are currently absent from `data/master_profile.json` and `data/resume_studio/resume.yaml`. Fix that.

1. **Rename Job Bot for resume use.** Propose 5 product-style names (e.g., pattern: what it does + credible; avoid "bot" — recruiters read "bot" as toy). Present them to John with a one-line rationale each and WAIT for his pick before writing it anywhere.
2. Mine both repos (`Job Bot/` and `PersonalFinanceOS/`) for **quantifiable, true** material: number of agents, pipeline stages, ATS engine, Gmail-sync classification, SQLite schema size, Streamlit dashboard, tech stack (Python, Streamlit, SQLite, MCP/agent orchestration, RenderCV/Typst). Extract 3–4 bullets per project in accomplishment form: *built X using Y, resulting in Z*.
3. Add a `projects` section to `master_profile.json` and `resume.yaml`. Evidence: the diff.

## Phase 2 — Dual-track tailoring (business vs tech), trial-and-error loop

Current routing lives in `job_bot/template_select.py`: `TECH_FIELDS = {"Data & Analytics", "Software / Engineering"}` → RenderCV/Typst engineering template; everything else → VMH business docx. The problem is not just routing — it's that the two tracks should **differ in content emphasis**, and today they mostly differ in styling.

Define the track contract first, in `docs/resume_track_contract.md`:

- **Business track** (audit, accounting, IT-risk, consulting, finance roles): experience-led. Work history and leadership on top; projects section short (2 lines max per project, framed as initiative/impact, not tech stack); keeps the exact VMH structure of John's approved resumes.
- **Tech track** (data, analytics, SWE-adjacent roles): project-led. The two renamed projects appear prominently with stack + architecture bullets; coursework/skills section expanded; experience compressed.
- Ambiguous fields (IT Audit / Tech Risk is deliberately business today — see the NOTE in `template_select.py`): decide per-JD by keyword evidence, and log which track was chosen and why into the tailoring output.

Then run this loop per track, using a real JD for each (pick one recent business JD and one tech JD from the `jobs` table; `data/sample_jd_deloitte_itrisk.txt` works for business):

1. `resume-tailor` produces the package via the normal pipeline (`tailor.py` → renderer).
2. Score it with `job_bot/ats_engine.py`. Record before/after.
3. **Recruiter due-diligence pass**: delegate to the `recruiter-reviewer` agent (`.claude/agents/recruiter-reviewer.md`) with the rendered output path, the JD, and the claimed track. It reviews the actual .docx/PDF render — formatting, section order, bullet quality, fabrication check — and returns `VERDICT: PASS|FAIL` plus a numbered defect list. It never edits; it only judges.
4. Fix every kill/major defect it reports. Re-render, re-score, re-submit to `recruiter-reviewer`.
5. Exit when: **recruiter-reviewer returns PASS** AND ATS score ≥ 85 AND zero contract violations. Both gates must pass on the same render — an ATS-optimized resume that a human recruiter would toss fails, and vice versa. Evidence each iteration: score delta + the verdict block verbatim.

Wire whatever the loop learned back into code (`tailor.py`, `template_select.py`, `resume_models.py`), not just into one-off outputs — the next unattended daily-pipeline run must benefit.

## Phase 3 — Fix the seniority/qualification filter, eval-driven

Symptom: search results include roles requiring many years of experience. `job_bot/seniority.py` already classifies intern < entry < mid < senior < lead < exec with `TARGET_MAX = "entry"`, `KEEP_MAX = "mid"` — so leaks mean either (a) call sites don't apply it, or (b) classification misses patterns.

1. **Build the eval set first.** Pull 30–50 real postings from the `jobs` table (mix of kept and should-have-been-dropped). Hand-label expected level in `tests/fixtures/seniority_eval.jsonl`. Include known hard cases: "Staff Accountant" (entry!), "Analyst III" (senior), years-in-JD-but-not-title, "Associate Director" (lead, despite 'associate').
2. Measure: run `seniority.classify()` over the set. Report accuracy and every false-keep (senior job that survived).
3. Audit **call sites**: `search_jobs.py`, `score_job.py`, `decide.py`/`decision_engine.py`, `newgrad.py` — confirm the filter actually gates search results AND the apply recommendation. A perfect classifier that isn't called is the likeliest bug.
4. Fix, re-run eval, iterate until false-keep rate ≤ 5% with zero regressions on the hard cases. Ship the eval as a permanent pytest so future edits can't silently break it.
5. Also gate on **qualifications**, not just title level: if a JD demands a certification or degree John doesn't have (check `master_profile.json`), down-rank and say why. Log dropped jobs with reasons so John can spot over-filtering — the failure mode in both directions matters.

## Phase 4 — Email → tracker → dashboard cadence

State the current truth in the final report so John has it on record: `gmail_sync.py` is a pure transform — the Gmail MCP call happens only in the agent layer, so email state (and therefore the Streamlit dashboard, which reads the DB) updates **only when the daily pipeline or an inbox-triager run is manually invoked**. Nothing is on a schedule today.

Verify `daily_pipeline_prompt.md` step 3.5 exercises the sync end-to-end, and confirm dedupe-by-Gmail-id holds on a double-run (evidence: run twice, row counts identical).

## Phase 5 — Hermes export (lock in what worked)

Once Phases 2–3 pass, the tuned workflows are proven private (Hermes-layer) assets. Convert them:

1. Use **skill-creator** to codify the resume trial-and-error loop as a local skill (`.claude/skills/resume-tailoring-loop/`) so future sessions run the tuned loop instead of rediscovering it.
2. Use **hermes-imports** to produce a sanitized, ECC-safe version of both the tailoring loop and the eval-driven filter-fix pattern: strip John's name, paths, employer names, and profile data; follow the skill's sanitization checklist and output contract. Save under `docs/prompts/exports/`.

## Final output contract

Report back with: per-phase pass/fail + evidence, files changed (paths), final ATS scores per track, seniority eval accuracy before → after, the email-cadence statement from Phase 4, and any decisions that still need John.
