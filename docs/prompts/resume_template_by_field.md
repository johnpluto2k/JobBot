# Prompt: field-based résumé template + carryover from last session

Paste this whole thing into Claude Code from the repo root. Part A is the carryover context from the last session (verbatim, so nothing gets lost); Part B is the new template-switching feature, finalized and ready to implement.

## Part A — carryover from last session (answer these first)

> Continuing work on the Job Bot résumé pipeline. Context from the last session:
> WHAT WAS DONE
> - Fixed a bug where the "Pantry Plate" project rendered twice (duplicate title +
>   stray tech-stack line) in the Résumé Lab / Resume Studio and every generated
>   résumé. Root cause: two malformed entries at the top of that project's `bullets`
>   in data/master_profile.json (a title line and a tech list that belong in the
>   header). Fixed defensively in job_bot/tailor.py `_select_project` via a new
>   `_is_project_meta_bullet` filter — master_profile.json was NOT edited.
> - Résumé Lab downloads now save as Lastname_Firstname_Company_Date (e.g.
>   Bae_John_dxc-technology_2026-07-06.docx) instead of resume.docx. Helper is
>   `tailor.resume_basename`; wired into both front-ends' download names
>   (job_bot/dashboard.py = Streamlit, job_bot/api.py = FastAPI). Files on disk
>   keep canonical names (resume.docx/.pdf/.yaml) so nothing else breaks.
> - Regenerated today's 3 application packages clean; regression tests
>   (python -m tests.test_pipeline) pass.
> KEY FACTS
> - "Resume Lab" = Resume Studio; there are TWO front-ends: dashboard.py (Streamlit)
>   and api.py (FastAPI). Keep them consistent.
> - Git repo is at the workspace root C:\ClaudeProjects, not the Job Bot folder.
> - Hard guardrails: never edit data/master_profile.json without explicit OK,
>   never send outreach, never submit applications (submit=False stays).
> OPEN ITEMS — pick up here:
> 1. Decide whether to clean the 2 junk bullets out of master_profile.json's
>    Pantry Plate project (code already suppresses them; this is source tidy-up).
> 2. These changes are uncommitted — commit if wanted (repo at C:\ClaudeProjects).
> 3. Optional: run the Résumé Lab UI and confirm a real download saves with the
>    new filename; and align the .yaml/.typ download names in dashboard.py with
>    the same pattern for consistency (currently only .pdf/.docx were changed).
> 4. Review/send the 3 regenerated drafts in data/applications/.

Verified current state (re-checked this session, so this is live, not assumed):
- The 2 junk "bullets" (`"Pantry Plate — Full-stack recipe & food-waste web app"` and the raw tech-stack CSV line) are **still present** in `data/master_profile.json`'s Pantry Plate project — item 1 is still open. Recommendation: clean them out now. The `_is_project_meta_bullet` filter in `tailor.py` is a good defensive guard to *keep* regardless (protects against the same import artifact recurring elsewhere), but the source data being wrong is a latent bug for any future code path that reads `bullets` directly without going through that filter (e.g. a LinkedIn-optimizer or export path that doesn't call `_select_project`). This edit needs explicit OK per the hard guardrail — say so explicitly when you paste this in.
- Changes are still uncommitted (no way to verify git status from this session — the git root is a level up from what's shared here). Recommendation: commit once the Part B changes below are also in, as one clean commit (or two: bugfix/naming, then the template feature) rather than leaving both uncommitted longer.
- Items 3 and 4 (manual UI check, review the 3 drafts) are genuinely manual/judgment steps — do them yourself when you're at the machine; nothing to automate there.

## Part B — new feature: auto-select résumé template by career field

**The ask:** tech/CS-track roles should render using a UMD CS/tech-style résumé format; business-track roles (accounting, audit, tax, finance) should keep using the UMD VMH-style format — the one you've actually been submitting. Right now renderer choice is 100% manual (`--renderer docx|rendercv` on the CLI, a radio button in Resume Studio) with no connection to what job is being applied to.

**What already exists that this builds on** (confirmed by reading the current code, not assumed):
- `job_bot.applications.classify_field(title, extra)` already classifies a posting into one of: `IT Audit / Tech Risk`, `Tax`, `Internal Audit`, `Risk & Compliance`, `Data & Analytics`, `Software / Engineering`, `Audit & Assurance`, `Finance / FP&A`, or `Other`.
- The docx/reportlab renderer (`render_docx.py` + `render_pdf.py`, the current default) already *is* the VMH-style format — it's what's been submitted historically. No new template needed on this side.
- The RenderCV renderer (`render_rendercv.py`) already defaults to the `engineeringresumes` theme — a RenderCV theme built for engineering/CS résumés, i.e. already a reasonable stand-in for "UMD CS/tech format." No new theme needed either, most likely — this is a wiring problem, not a from-scratch design problem.

**Changes:**

1. Add a small, explicit mapping — a new `job_bot/template_select.py` (or a function in `tailor.py`, your call) —
   ```python
   TECH_FIELDS = {"Data & Analytics", "Software / Engineering"}
   # "IT Audit / Tech Risk" is deliberately treated as business/VMH by default —
   # it's still an audit/risk-track role at accounting-style firms, not a SWE/CS
   # résumé. Flag this back to John rather than assuming; easy to flip if he
   # disagrees.

   def renderer_for_field(field: str) -> str:
       """'rendercv' (CS/tech template) or 'docx' (VMH/business template)."""
       return "rendercv" if field in TECH_FIELDS else "docx"
   ```
2. In `generate.py`: change `--renderer`'s default from `"docx"` to `None` (so "not specified" is distinguishable from "explicitly docx"). After parsing the JD (`job = parse_jd(...)`), compute `field = classify_field(job.title or "", job.raw_text or "")`, then `renderer = args.renderer or renderer_for_field(field)`. Print the decision (`f"  · field: {field} -> renderer: {renderer}"`) so it's visible in the CLI output, and use `renderer` (not `args.renderer`) for the rest of the function. An explicit `--renderer` flag always wins over the auto-pick.
3. Write a small `meta.json` into each `app_dir` alongside `checklist.md` — `{"field": field, "renderer": renderer}` — so Resume Studio can read back *why* a given application used the template it did, instead of only the CLI seeing that decision.
4. Resume Studio, both front-ends:
   - **Streamlit (`dashboard.py`, `with tab_resume:`)**: when `studio_src` is an existing application folder, read its `meta.json` if present and default the `studio_renderer` radio to match (`"Typst PDF (RenderCV)"` for tech, `"Word (.docx)"` for business) instead of always defaulting to the radio's first option. When building fresh from the master profile (no target JD), fall back to whatever field the first `profile["targets"]["target_roles"]` entry classifies as.
   - **FastAPI (`api.py`) + React (`web/src/components/ResumeStudioTab.tsx`)**: have `/api/resume-studio/yaml` (and wherever else makes sense) include the classified `field` and `suggested_renderer` in its response, and update `ResumeStudioTab.tsx` to default its renderer toggle from that value instead of a hardcoded default — keep both front-ends behaviorally consistent, per the standing rule from last session.
   - In both UIs, this is a *default*, not a lock — John can still flip the radio/toggle manually, same as today.

**Acceptance check:** generate one tech-track posting (e.g. a "Data Analyst" or "Software Engineer" JD) and one business-track posting (e.g. an "Audit Associate" JD) through `python -m job_bot.generate` with no `--renderer` flag, and confirm the first auto-picks RenderCV/Typst and the second auto-picks docx. Open Resume Studio in both front-ends against each of those two application folders and confirm the renderer control defaults to match. Run `python -m tests.test_pipeline` to confirm nothing existing broke, and add one regression test asserting `renderer_for_field` returns the expected value for a couple of known fields.
