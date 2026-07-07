# Prompt: Job Bot adjustments — safer scraping, cheaper LLM calls, LaTeX resume

Paste this into Claude Code from the `Job Bot` repo root. Three independent workstreams — hand them off one at a time or all at once.

---

## 1. De-risk the Indeed/LinkedIn scraping in `job_bot/jobsearch.py`

Current state: `search()` calls JobSpy's `scrape_jobs()` unauthenticated (no LinkedIn login cookie — good, keep it that way, since authenticated scraping ties risk to the account, not just an IP). It already fails soft (catches exceptions, returns `[]` with a message pointing at manual JD paste).

Known behavior as of mid-2026: Indeed tolerates JobSpy well with effectively no rate limiting. LinkedIn throttles around the 10th results page per IP and returns 429s beyond that; its public jobs page structure changes periodically and breaks scrapers until JobSpy updates. This isn't really an "evade detection" problem to engineer around — it's closer to "don't hit LinkedIn hard enough to get IP-throttled, and have a graceful fallback when it happens."

Changes to make:

- Add a retry-with-backoff around the `scrape_jobs()` call in `search()` — on a 429/rate-limit-shaped exception, wait and retry once (e.g. 30–60s), then give up cleanly (it already does the "give up cleanly" part).
- Default `--sites` in `search_jobs.py` to `indeed` only, with LinkedIn opt-in via an explicit flag — Indeed is the reliable source; treat LinkedIn results as a bonus, not something to depend on every run.
- Cap `results_wanted` conservatively by default (e.g. 15–20, which is already the default) and don't fan out to LinkedIn across many search terms back-to-back in the same session — add a small delay (2–5s) between site calls if `sites` has more than one entry.
- Add a `data/scrape_log` table (or reuse `jobs`) to record term+timestamp of each scrape, so re-running the same search within a short window (e.g. 1 hour) warns and skips instead of re-hitting the site.
- No change needed to `autofill.py` — it already never auto-submits and requires a human review pass, which is the right posture for ATS platform pages (Greenhouse/Lever/Workday etc. — a different risk profile than LinkedIn/Indeed's own anti-scraping).
- Leave a comment in `jobsearch.py` noting this is personal-use, low-volume, unauthenticated scraping — not a basis for scaling up request volume later.

---

## 2. Cut LLM cost in `job_bot/tailor.py` and `job_bot/cover_letter.py`

Reality check on "run it through Vercel to make it cheaper": Vercel doesn't change what Anthropic charges per token — a Vercel AI Gateway is a pass-through at the provider's list price, no markup, whether you call it from Vercel or from this local Python script. Vercel's actual cost lever is its semantic cache, which only helps if requests repeat near-verbatim (roughly 20–40% hit rate on repeat queries) — not obviously true here since every JD is different. Where Vercel would matter is if this stops being a local CLI tool and becomes a hosted web app; that's a hosting/architecture decision, not a cost-per-tailor-run decision. Skip it for now and fix the actual cost drivers, which are all in the Python code:

- **Right-size the model per call.** `_llm_rewrite()` in `tailor.py` (bullet rewriting) is a mechanical rephrasing task — route it to Claude Haiku instead of the Sonnet default in `config.ANTHROPIC_MODEL`. Keep Sonnet for `_llm_cover_letter()` in `cover_letter.py`, which needs more judgment. Add a second config var (`ANTHROPIC_MODEL_FAST`) for this.
- **Add prompt caching.** Both `_llm_rewrite()` and `_llm_cover_letter()` independently re-serialize the same profile facts (education, experience, skills) into the prompt on every `generate` run. Split each prompt into a cacheable block (the static profile JSON) and a small per-job block (JD text, target role) using Anthropic's `cache_control` on the message content blocks. Across a session generating multiple applications back-to-back, this turns repeated ~$3/MTok input reads into ~$0.30/MTok cache reads for the shared profile portion.
- **Consider the Batches API** for any run where the user is generating several applications at once and doesn't need results in real time (50% off both calls). Not worth it for single ad-hoc `generate` runs — only worth wiring up if there's a "tailor for these 5 jobs" batch mode.
- **Trim `max_tokens`.** `_llm_rewrite` requests `max_tokens=2000` for what's usually a handful of one-line bullets — cap closer to the actual expected output size to avoid over-provisioning (this affects latency more than cost with Claude's pricing model, but tightening it is still worth doing).

Acceptance check: run `python -m job_bot.generate` twice in the same session for two different JDs and confirm (via `anthropic` response usage fields) that the second call shows cache-read tokens on the profile block.

---

## 3. Move resume rendering from Word/reportlab to a LaTeX/Overleaf pipeline

Current state: `render_docx.py` (python-docx) and `render_pdf.py` (reportlab) both hand-build the resume layout in code from the `TailoredResume` dataclass (`resume_models.py`). Editing the layout means editing Python drawing code — hence the interest in "coding" the resume instead of hand-formatting a Word doc.

Recommended tool: **RenderCV** — an open-source resume builder (17k+ GitHub stars) where you write the resume as YAML and it renders to a polished LaTeX-based PDF. It has ready-made themes published as Overleaf templates, so the same YAML can be edited/rendered either via the RenderCV CLI locally or pasted into Overleaf for visual tweaking, and it's plain text so it's git-diffable.

Implementation:

- Add `job_bot/render_rendercv.py` with a `render_rendercv(resume: TailoredResume, out_path: Path) -> Path` function that maps the existing `TailoredResume` fields (name, contact_line, summary, education, experience, leadership, projects, skills, certifications) into RenderCV's YAML schema, writes it to `app_dir/resume.yaml`, then shells out to `rendercv render` to produce the PDF.
- Add `rendercv` to `requirements.txt`.
- In `generate.py`, add a `--renderer {docx,rendercv}` flag (default can stay `docx` until the YAML mapping is verified against a couple of real JDs) so both pipelines coexist rather than a risky one-shot swap.
- Pick (or ask the user to pick) a RenderCV theme that stays ATS-safe: single column, no icons/graphics/tables in the parsed text layer — some RenderCV themes use icons for contact info that can render as unparseable glyphs to ATS text extractors, so verify the chosen theme's text-extraction output (e.g. `pdftotext`) looks clean before making it the default.
- Once validated, the `.yaml` source can be pushed to a git repo and opened directly in Overleaf via Overleaf's GitHub sync, so resume edits happen in a versioned text file instead of a Word doc.

Acceptance check: generate one real application with `--renderer rendercv`, confirm the PDF is one page, run it through the existing ATS scorer (`ats_engine.score`) to confirm parity with the docx version, and confirm `pdftotext` output is clean (no missing sections, no icon glyphs replacing text).

---

## Other things worth a look (lower priority)

- `tailor.py` and `cover_letter.py` each independently decide `use_llm = config.has_llm()` and silently fall back to templates on any exception — good for resilience, but worth logging *which* runs fell back so cost/quality isn't silently degrading without the user noticing.
- `jobsearch.py`'s `save_jobs()` swallows all exceptions per-row (`except Exception: pass`) — fine for resilience, but worth at least counting/logging failures so a schema mismatch doesn't fail silently forever.
- No automated tests found for the tailoring/rendering pipeline — worth a basic regression test that runs `generate.py --no-llm` against a fixture JD and asserts the docx/pdf/rendercv outputs all produce a valid one-page file, so renderer changes don't silently break output.
