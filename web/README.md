# Job Bot — React Dashboard

The single React dashboard for the Job Bot Career OS (Vite + React + TypeScript,
Tailwind v4, shadcn/ui primitives). It reads from a FastAPI layer
(`job_bot/api.py`) that reuses the **same** logic as the original Streamlit app
(`applications.summary` / `build_applications`, `growth.build_plan`,
`network_map.build_map`, `offers.compare`, and the Phase 2–3 scorer), so the
numbers and verdicts match exactly.

**13 pages behind a grouped sidebar** (drawer below the `md` breakpoint; the
active page persists via `localStorage`, no router dependency):

- **Overview** — Overview (KPIs + funnel + field mix + profile), Coach (LLM
  chat grounded in the live pipeline)
- **Pipeline** — Applications (reconciled tracker), Pipeline (scored postings,
  searchable and sortable), Companies (company-first tracker — **Log a job**
  intake form, overdue check-ins, and the posting watcher's per-company
  `watching · <platform>` and "N new" badges), Find Jobs (live board search by
  cycle + track, job-board picker, results-per-role slider)
- **Build** — Resume (one pasted JD → ATS + network verdict, job summary, and a
  tailored one-page résumé; the RenderCV YAML editor and Typst PDF preview live
  under "Advanced"), LinkedIn optimizer
- **Network & Growth** — Network (coverage + gaps), Growth
  (certs/projects/insights), Offers (COL-adjusted comparison), Company Brief,
  Interview Lab (answer analysis)

Only Overview reads `/api/summary`, and only Overview is gated on it — a
summary failure used to replace every page with an error card. `useAsync` keeps
the last good data when a refetch fails, so a transient error annotates the
table rather than destroying it.

In single-server mode FastAPI serves this UI *and* the API on one port, fully
replacing the Streamlit dashboard for daily use.

**Auth:** the app mounts behind a `SignInScreen` — everything under `/api/*`
(except `health` / `auth/status`) requires the Google session cookie minted by
`/auth/callback` (see `job_bot/google_auth.py`). After sign-in the header shows
a `SyncIndicator` chip (last Gmail sync / new items / manual "sync now") and a
sign-out button; Gmail auto-syncs every 15 minutes server-side.

## Architecture

```
┌────────────┐   /api/*   ┌─────────────────┐   reuses   ┌──────────────────┐
│  React app │ ─────────▶ │  FastAPI (8000) │ ─────────▶ │ applications.py  │
│ (Vite 5173)│  (proxied) │   job_bot/api   │            │ + SQLite job_bot │
└────────────┘            └─────────────────┘            └──────────────────┘
```

The Vite dev server proxies `/api/*` to `http://127.0.0.1:8000` (see
`vite.config.ts`), so there's no CORS friction in development.

## Run it (two terminals, from the project root)

**1 — backend:**

```bash
pip install -r requirements.txt          # first time only (adds fastapi, uvicorn)
uvicorn job_bot.api:app --reload --port 8000
```

**2 — frontend:**

```bash
cd web
npm install                              # first time only
npm run dev                              # http://localhost:5173
```

## Endpoints (job_bot/api.py)

| Route                   | Returns                                                      |
| ----------------------- | ----------------------------------------------------------- |
| `GET /api/profile`      | Name, contact, location, avatar (data URI)                  |
| `GET /api/overview`     | Education, skills, experience, targets, certifications      |
| `GET /api/summary`      | Funnel counts, response/interview rates, field mix          |
| `GET /api/applications` | One reconciled record per company applied to                |
| `GET /api/jobs`         | Live scored postings, ranked by priority (`?status=&limit=`)|
| `GET /api/network`      | Company-by-company coverage + target gaps                   |
| `GET /api/growth`       | Prioritized growth plan (certs, projects, insights)         |
| `GET /api/offers`       | COL-adjusted offer comparison (`?money=&growth=&fit=`)      |
| `POST /api/score`       | Live ATS + network verdict for a pasted JD                  |
| `GET /api/cycles`       | Hiring cycles (from grad date), career tracks, job-board sites + defaults |
| `POST /api/search`      | Live job-board search for chosen tracks/cycle/sites (scrapes) |
| `POST /api/intake`      | Manually log a job (url, company, title, portal, status)    |
| `GET /api/companies`    | List tracked companies (`?due_for_check=true` for overdue)  |
| `GET /api/companies/{id}` | One tracked company                                       |
| `PATCH /api/companies/{id}` | Mark a company checked / reschedule next check          |
| `GET /api/watch/status` | Which companies the posting watcher polls + last-pass results |
| `POST /api/watch/run`   | Run a watcher pass now (`?limit=`, `?all_companies=`)       |
| `GET /api/resume-studio/sources` | Résumé sources (master profile + generated application folders) |
| `GET /api/resume-studio/yaml`    | RenderCV YAML for a source (`?source=`) + suggested renderer |
| `POST /api/resume-studio/render` | Typeset edited YAML via RenderCV/Typst → `pdf_b64` + `.typ` text |
| `GET /api/resume-studio/docx`    | Classic python-docx résumé for a source (`docx_b64`)  |
| `POST /api/brief`       | Company research brief (+ LLM narrative)                    |
| `POST /api/linkedin`    | LinkedIn headline/About/skills audit                        |
| `POST /api/recording`   | Interview answer analysis (STAR, pacing, fillers)           |
| `POST /api/coach`       | Career Coach chat turn (grounded in the live pipeline)      |
| `GET /auth/login`       | Start the Google OAuth consent flow                         |
| `GET /auth/callback`    | Store refresh token + set the session cookie                |
| `GET /api/auth/status`  | `{logged_in, email, configured}` (open, no cookie needed)   |
| `POST /api/auth/logout` | Clear the session                                           |
| `GET /api/sync-status`  | Last Gmail sync, new-item counts, running flag              |
| `POST /api/sync-now`    | Run a Gmail sync immediately                                |
| `GET /api/health`       | Liveness + DB presence (open, no cookie needed)             |

## Layout

- `src/lib/api.ts` — typed client + status→badge mapping
- `src/lib/useAsync.ts` — tiny fetch-on-mount hook (no react-query needed); keeps
  the last good data when a refetch fails
- `src/lib/search.ts` — `matches()`, the multi-term table search predicate
- `src/components/ui/*` — shadcn primitives (card, badge, button, table, input, textarea)
- `src/components/*` — dashboard blocks (KpiCard, PipelineFunnel, FieldMix, ErrorNote, tables, header) + one component per page, incl. `CompanyTrackerTab.tsx`
- `src/components/LogJobForm.tsx` — the **Log a job** intake form (Companies page)
- `src/components/TableToolbar.tsx` — search box + "N of M" count for long tables
- `src/components/SignInScreen.tsx` — Google sign-in gate shown until the session cookie exists
- `src/components/SyncIndicator.tsx` — header chip: last Gmail sync / new items / manual sync
- `src/components/ResumeTab.tsx` — the Resume page: JD box → score, job summary and
  tailored résumé, with the YAML editor and Typst preview under "Advanced"
- `src/App.tsx` — auth gate + grouped sidebar nav (state in `localStorage`)
- `src/index.css` — Job Bot design tokens ported to shadcn's CSS-variable contract

`tsconfig.app.json` has `strict: true`. Note that plain `npx tsc --noEmit` from
`web/` checks **nothing** — the root tsconfig is a solution file with
`"files": []`. Use `npx tsc -p tsconfig.app.json --noEmit`, or `npm run build`,
which runs `tsc -b`.

## Production build

```bash
npm run build      # → web/dist (static). Serve behind the same origin as the API
                   #   and drop the CORS allow-list in job_bot/api.py.
```
