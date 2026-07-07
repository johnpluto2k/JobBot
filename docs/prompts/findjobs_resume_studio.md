# Prompt: Expand the Find Jobs tab + add a Resume Studio tab

Paste this into Claude Code from the `Job Bot` repo root. Two independent pieces.

## Part 1: Find Jobs tab (`job_bot/dashboard.py`, `with tab_find:` block, and `job_bot/newgrad.py`)

Current state: the "Find Jobs" tab already searches by graduation cycle + career track via `newgrad.run()`, with a "Results per role" slider capped at 25 and a "Posted within" slider up to 336 hours — but no site selector, and it always searches whatever `newgrad.run()`/`search()` defaults to (`indeed` + `linkedin`, hardcoded in the UI caption). `newgrad.run()` already accepts a `sites` parameter under the hood (the CLI exposes `--sites`); the Streamlit tab just doesn't expose it.

Changes:

- **Site filter**: add a multiselect in the `tab_find` search row (next to location/remote/results/freshness) listing `indeed, linkedin, glassdoor, google, zip_recruiter`, and pass the selection into `newgrad.run(sites=...)`. Default to `["indeed"]` only, with the others opt-in — this matches the earlier scraping-risk guidance (Indeed tolerates JobSpy well with no real rate limiting; LinkedIn throttles around page 10/IP, so it should be something John turns on deliberately, not something that fires by default on every search). Update the "Searching N roles across LinkedIn/Indeed/Glassdoor…" spinner caption to reflect the actual selected sites instead of a hardcoded list.
- **More listings**: raise the "Results per role" slider range (currently `5, 25, 10`) to something like `5, 50, 20` so a search pulls deeper per query when John wants more coverage, and bump the "Posted within" slider's practical default up slightly if a wider net is wanted. Note in the UI (a `st.caption`) that pushing this high across many tracks/sites means more requests per search — pair it with the Part 1 scraping guidance already in place (backoff, Indeed-first).
- **More career fields**: `newgrad.TRACKS` currently has 5 tracks (Accounting & Audit, Finance & FP&A, Data & Analytics, IT & Cybersecurity, Software & Engineering). Add a handful more so the multiselect covers more ground — e.g. `"Consulting"`, `"Marketing & Communications"`, `"Operations & Supply Chain"`, `"Human Resources"` — each as a list of `(search term, is_remote)` tuples following the existing pattern. Leave `DEFAULT_TRACKS` as-is unless John wants the defaults widened too; new tracks should just become available in the "Career tracks to search" multiselect.

Acceptance check: run the dashboard, open Find Jobs, confirm the site multiselect appears and actually changes which sites get hit (check `res["per_query"]` / the per-search breakdown expander), confirm the new tracks show up in the track picker, and confirm a 50-results-per-role search still completes without erroring.

## Part 2: New "Resume Studio" tab — resume as code, round-tripped through Overleaf

Current state: resume generation only exists as a CLI flow (`python -m job_bot.generate`), producing a `.docx` (python-docx) and `.pdf` (reportlab). There's no dashboard tab for building/editing a resume at all, and the earlier RenderCV/LaTeX renderer recommendation (`job_bot/render_rendercv.py`) hasn't been implemented yet — this prompt covers both the backend renderer and the new tab, so do them in order.

**2a. Backend — `job_bot/render_rendercv.py`** (if not already present):
- `render_rendercv(resume: TailoredResume, out_dir: Path) -> dict` that maps the existing `TailoredResume` fields (`resume_models.py`) into RenderCV's YAML schema, writes `out_dir/resume.yaml`, shells out to `rendercv render` (add `rendercv` to `requirements.txt`), and returns paths to the generated `.yaml`, `.tex`, and `.pdf`.
- Pick an ATS-safe RenderCv theme (single column, no icon glyphs standing in for text in the parsed layer) — verify with `pdftotext` on the output before wiring it into the UI.

**2b. New Streamlit tab — "Resume Studio"** in `dashboard.py` (add to the `st.tabs([...])` call and the corresponding `with tab_resume:` block):
- Let John either load the tailored resume from his most recent `job_bot.generate` run for a given application, or build straight from `master_profile.json` if no target JD is picked.
- Show the RenderCV YAML in an editable `st.text_area` — this *is* "resume as code": John can hand-edit bullet order, wording, section content directly as text, not through a GUI form.
- A "Render" button that writes the edited YAML and calls `render_rendercv()`, then previews the resulting PDF inline (embed via base64 `<iframe>` or `st.pdf` if the installed Streamlit version has it) with a download button.
- An **"Open in Overleaf"** button: base64-encode the generated `.tex` file and build a link of the form:
  `https://www.overleaf.com/docs?snip_uri=data:application/x-tex;base64,<encoded>`
  This opens the resume as a new Overleaf project directly from the encoded content — no hosting, no Overleaf account API/auth needed, confirmed still supported as of mid-2026. Render it as an `st.link_button("Open in Overleaf", url)`.
- Be upfront in the UI (a caption, not a promise) that the Overleaf round-trip is one-way by default: edits made *inside* Overleaf need to be downloaded and pasted back over the local `.tex`/`.yaml` manually. A fully scripted two-way sync would mean adopting `pyoverleaf` (an unofficial PyPI package wrapping Overleaf's internal API via session cookies) — flag this as a possible future stretch goal only, since it's unofficial and could break if Overleaf changes its internals; don't build it now.
- Keep the existing docx/reportlab path available as a renderer choice (radio: "LaTeX (RenderCV)" / "Word (.docx)") rather than replacing it outright, so `generate.py`'s existing flow keeps working.

Acceptance check: generate one real tailored resume through the new tab, confirm the YAML is genuinely editable and re-renders correctly after a hand edit, confirm the Overleaf link actually opens the resume as a new project in Overleaf, and confirm the docx fallback still works unchanged.
