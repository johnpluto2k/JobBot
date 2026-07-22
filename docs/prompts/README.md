# Claude Code prompts

One-off prompts written to be pasted into a Claude Code session at the repo
root. Kept for the record of *why* a batch of changes was made; each is a spec,
not living documentation — the code and `README.md` are the source of truth
once a prompt is implemented.

| Prompt | Status | What it changed |
| --- | --- | --- |
| [`tuneups_adjustments.md`](tuneups_adjustments.md) | ✅ done (2026-07-02) | Safer scraping defaults, prompt-cached/right-sized LLM calls, RenderCV resume pipeline |
| [`ai_text_quality.md`](ai_text_quality.md) | ✅ done (2026-07-05) | Anti-cliché style guardrails (`job_bot/writing_style.py`) for bullets, cover letters, LinkedIn About; COACH.md style section |
| [`personal_section_ui.md`](personal_section_ui.md) | ✅ done | Personal section + avatar corner in the Streamlit dashboard |
| [`findjobs_resume_studio.md`](findjobs_resume_studio.md) | ✅ done (2026-07-05 Streamlit; 2026-07-16 React port) | Find Jobs site filter, deeper results, 4 new tracks; Resume Studio tab. Deviation: RenderCV 2.x emits Typst, not LaTeX, so the "Open in Overleaf" button became a download-`.typ`-for-typst.app flow (Overleaf would require pinning `rendercv<2`). React port + sidebar nav landed via [`frontend_redesign.md`](frontend_redesign.md) |
| [`resume_template_by_field.md`](resume_template_by_field.md) | ⏳ pending | Auto-select résumé template by career field: tech/CS fields (Data & Analytics, Software / Engineering) → RenderCV/Typst `engineeringresumes` theme; business fields (accounting/audit/tax/finance) → existing docx/VMH renderer. Carries forward the Pantry Plate source-cleanup + commit decision from the prior session. |
| [`frontend_redesign.md`](frontend_redesign.md) | ✅ done (2026-07-16) | Finished the stalled sidebar-nav migration (grouped sidebar replaces the 12-tab horizontal strip, drawer below `md`), mounted `ResumeStudioTab` under Build, finished `FindJobsTab`'s site picker + results slider, standardized primary/secondary action-button placement, and unified errors on the shared `ErrorNote`. |
