# Prompt: Merge "Score a JD" + "Resume Studio" into one "Resume" page

Copy everything below this line into Claude Code (run from the `Job Bot` repo root).

---

## Goal

Replace the two separate tabs **Score a JD** (`web/src/components/ScoreTab.tsx`) and **Resume Studio** (`web/src/components/ResumeStudioTab.tsx`) with a single **Resume** page that runs one flow from one input:

1. **JD input box** — I paste a job description (plus optional posting URL and company override, same as ScoreTab today) and click **Analyze**.
2. **Score box** — shows the live ATS match + network verdict (exactly what `POST /api/score` already returns: overall score bar, keyword match, ranked gap analysis, recommended actions, warm contacts).
3. **Job summary box** — a new box summarizing the job and its relevant information extracted from the parsed JD: title, company, location, role type, seniority, market tier, remote flag, ATS platform, GPA cutoff, years of experience required, and the required/preferred keyword lists. If an Anthropic key is configured (`config.has_llm()`), also include a short 2–3 sentence prose summary of the role; otherwise skip the prose gracefully.
4. **Tailored resume** — while the score and summary display, the page also generates a resume tailored to that JD using the existing tailoring engine, renders it, and shows it inline with download buttons. The resume must fit on **one page**.

Everything lives on **one page** — no navigating between tabs to complete this flow.

## How to work: orchestrate with subagents

Use the Task/Agent tool to parallelize this — don't do it all in one context. Suggested plan:

1. **Scout (Explore agent, first)**: launch one read-only Explore agent to map everything the workers will need and return a condensed brief: the exact JSX blocks in `ScoreTab.tsx` worth porting verbatim, the render/download/YAML-editor pieces of `ResumeStudioTab.tsx`, the signatures of `tailor_resume`, `resume_to_rendercv_dict`, `render_yaml_file`, `render_docx`, `renderer_for_field`, `classify_field`, and how existing endpoints in `job_bot/api.py` structure soft errors. Do not start implementation until this brief is back.
2. **Lock the API contract yourself (main context)**: before spawning workers, write the exact request/response JSON shapes for `POST /api/tailor` (and any docx variant) plus the `page_count` addition to the render response, and paste that contract into BOTH worker prompts. This is the only coupling point between the two workers — freezing it first is what makes them safe to run in parallel.
3. **Two parallel implementation agents** (launch in a single message so they run concurrently):
   - **Backend agent**: implements `/api/tailor`, the one-page `page_count` check in `studio_render`, and the pytest for the no-LLM path. Touches only `job_bot/`.
   - **Frontend agent**: implements `ResumeTab.tsx`, the `api.ts` client additions typed straight from the frozen contract, and the `App.tsx` nav/localStorage changes. Touches only `web/src/`.
   The disjoint file sets mean no merge conflicts; each agent's prompt should include the contract, the scout brief, and the relevant "Backend changes" / "Frontend changes" section below.
4. **Integrate + verify (main context, then a review agent)**: wire the two halves together, run the end-to-end check in "Verify before finishing", then spawn a fresh code-review agent that did NOT write the code to adversarially review the diff — contract mismatches between `api.ts` types and the actual endpoint responses, unhandled `{error}` shapes, dangling imports from the deleted tabs, layout-jump regressions. Fix what it finds before calling it done.

If any agent reports a blocker that changes the contract (e.g. the docx path needs a different shape), stop, update the contract in both places, and re-dispatch only the affected agent — don't let the two sides drift.

## Current architecture (read these files first)

- Frontend: React + TypeScript + Vite in `web/`. Nav/tabs defined in `web/src/App.tsx` (`PageKey` union + `NAV` array; the current keys are `studio` and `score`, persisted to localStorage under `jobbot.page`). Typed API client in `web/src/lib/api.ts`.
- Backend: FastAPI in `job_bot/api.py`.
  - `POST /api/score` — parses the JD (`jd_parser.parse_jd`), scores it (`ats_engine.score`), looks up warm contacts (`connections.matches_for_company`), and decides network-vs-cold (`decision_engine.decide`). Returns `{job, ats, decision}`.
  - `GET /api/resume-studio/yaml`, `POST /api/resume-studio/render`, `GET /api/resume-studio/docx` — the resume-as-code flow. `render` typesets RenderCV YAML via Typst and is slow (~15–30s).
- Tailoring engine: `job_bot/tailor.py` → `tailor_resume(profile, job, use_llm=...)` returns a `TailoredResume` (already designed to produce one-page output via `MAX_BULLETS` / `MAX_ROLES`). `job_bot/render_rendercv.py` → `resume_to_rendercv_dict(resume)` converts it to RenderCV YAML and `render_yaml_file(path, outdir)` typesets the PDF. `job_bot/render_docx.py` → `render_docx(resume, path)` for the .docx variant. `job_bot/template_select.py` → `renderer_for_field(field)` picks the suggested renderer per career field.
- `JobPosting` (in `job_bot/jd_models.py`) already carries every field the job-summary box needs: `title, company, location, role_type, seniority, market_tier, remote, ats_platform, gpa_cutoff, years_experience, required_keywords, preferred_keywords`.

## Backend changes

1. **Add `POST /api/tailor`** in `job_bot/api.py`, request body `{jd: str, url?: str, company?: str}` (same shape as `ScoreRequest`). It should:
   - Parse the JD once with `parse_jd(jd, url=url, use_llm=config.has_llm())`, apply the company override.
   - Build the job summary payload from the `JobPosting` fields listed above, plus the optional LLM prose summary.
   - Call `tailor_resume(profile, job, use_llm=config.has_llm())`, classify the field (`applications.classify_field` on the job title/target role) and get `suggested_renderer` via `renderer_for_field`.
   - Return `{summary: {...}, yaml: <RenderCV YAML string via resume_to_rendercv_dict>, field, suggested_renderer}` — do **not** typeset the PDF in this endpoint. Return `{error: ...}` instead of a 500 on failure, matching the style of the other endpoints.
2. **Reuse `POST /api/resume-studio/render` for typesetting** — the frontend sends the YAML from `/api/tailor` to it. Keep `/api/score` unchanged.
3. **One-page guarantee**: after rendering, check the PDF page count in `studio_render` (e.g. via `pypdf`/`PdfReader` or the rendercv output metadata). If the tailored resume comes out longer than one page, return `page_count` in the render response so the UI can warn; additionally, in `/api/tailor`, prefer the existing `MAX_BULLETS`/`MAX_ROLES` caps — do not raise them. If page count > 1, the UI shows a notice ("trimmed for one page" guidance) rather than silently shipping a 2-page resume.

## Frontend changes

1. **Create `web/src/components/ResumeTab.tsx`** (new combined page). Layout, top to bottom:
   - **Input card**: JD textarea + optional URL and company inputs + one **Analyze** button (disabled while running or when JD is empty). This is the only trigger for the whole flow.
   - On Analyze, fire **`api.score(...)` and `api.tailor(...)` concurrently**. As soon as `tailor` resolves, immediately call `api.studioRender(yaml)` to typeset the PDF in the background. Each box has its own loading state so results appear progressively: score and summary fill in fast; the resume card shows a "Typesetting via Typst — usually 10–30s" spinner until the PDF arrives (reuse the existing copy from ResumeStudioTab).
   - **Results row** (`grid lg:grid-cols-2`): left = **Score box** (port the verdict banner, keyword match, gap analysis, actions, and warm-contacts cards from ScoreTab — reuse the existing JSX/subcomponents rather than rewriting); right = **Job summary box** (new card: role facts as labeled rows/badges, keyword chips for required vs preferred, optional prose summary).
   - **Tailored resume card**: inline PDF preview (`iframe` with the base64 data URI, same as ResumeStudioTab), download buttons for `resume.pdf`, `resume.yaml`, `resume.typ`, and `resume.docx` (docx: render client-side is not possible — add a small backend path or reuse `render_docx` via a new `POST /api/tailor/docx {yaml or jd}`; simplest is to have `/api/tailor` also return nothing extra and add `POST` variant of the docx endpoint that accepts the tailored resume — pick the cleanest option and document it). Show the one-page status: green check "Fits on one page" or amber warning if `page_count > 1`.
   - **Advanced: collapsible "Edit YAML" section** at the bottom (collapsed by default) containing the RenderCV YAML editor + "Re-render PDF" button, so the resume-as-code editing power of Resume Studio isn't lost. Pre-fill it with the tailored YAML from the analyze run. Keep the "Start from" source picker (master profile / application folders) inside this advanced section too, so existing application-folder workflows still work.
2. **Update `web/src/lib/api.ts`**: add the `tailor` client method + `TailorResult` types (summary fields, yaml, field, suggested_renderer, error). Add `page_count` to `StudioRender`.
3. **Update `web/src/App.tsx`**:
   - Replace the `studio` and `score` entries in `PageKey` and `NAV` with a single `resume` entry — label **"Resume"**, icon `Sparkles` (or `FileCode2`), in the "Build" section.
   - Migrate the localStorage value: if the saved `jobbot.page` is `studio` or `score`, map it to `resume` instead of falling back to overview.
   - Route `case 'resume': return <ResumeTab />`.
4. **Delete** `ScoreTab.tsx` and `ResumeStudioTab.tsx` once their pieces are ported (or keep them temporarily and delete at the end — but the final state has no dangling imports/dead tabs).

## Constraints & style

- Don't fabricate resume content — the tailoring engine only reorders/rewrites real profile material; keep that guarantee.
- Match the existing UI conventions: shadcn-style `Card`/`Button`/`Badge`/`Textarea` components from `web/src/components/ui/`, `lucide-react` icons, CSS variables like `var(--primary)` / `var(--status-green)`, `ErrorNote` for errors, reserved-height status regions so layout doesn't jump (see ResumeStudioTab).
- Every fetch handles the `{error: ...}` soft-error shape inline; no unhandled 500s.
- TypeScript strict; run `npm run build` in `web/` and fix any type errors.

## Verify before finishing

1. `uvicorn job_bot.api:app --port 8000` + `cd web && npm run dev` — paste a real JD, click Analyze once, and confirm: score box, job summary box, and one-page tailored resume PDF all appear on the single Resume page with progressive loading.
2. `POST /api/tailor` returns valid RenderCV YAML that `POST /api/resume-studio/render` typesets without error, and the PDF is one page.
3. Old localStorage values `studio`/`score` land on the new Resume page; no console errors; `npm run build` passes; existing tests (`pytest`) still pass, and add a test for the new `/api/tailor` endpoint (no-LLM path so it runs offline).
