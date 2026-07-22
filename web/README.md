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
- **Pipeline** — Applications (reconciled tracker), Pipeline (scored
  postings), Find Jobs (live board search by cycle + track, job-board picker,
  results-per-role slider)
- **Build** — Resume Studio (editable RenderCV YAML → Typst PDF, plus the
  classic `.docx`), Score a JD (interactive ATS + network verdict), LinkedIn
  optimizer
- **Network & Growth** — Network (coverage + gaps), Growth
  (certs/projects/insights), Offers (COL-adjusted comparison), Company Brief,
  Interview Lab (answer analysis)

In single-server mode FastAPI serves this UI *and* the API on one port, fully
replacing the Streamlit dashboard for daily use.

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
| `GET /api/resume-studio/sources` | Résumé sources (master profile + generated application folders) |
| `GET /api/resume-studio/yaml`    | RenderCV YAML for a source (`?source=`) + suggested renderer |
| `POST /api/resume-studio/render` | Typeset edited YAML via RenderCV/Typst → `pdf_b64` + `.typ` text |
| `GET /api/resume-studio/docx`    | Classic python-docx résumé for a source (`docx_b64`)  |
| `POST /api/coach`       | Coach chat turn grounded in the live snapshot               |
| `POST /api/brief`       | Company research brief (+ LLM narrative)                    |
| `POST /api/linkedin`    | LinkedIn headline/About/skills audit                        |
| `POST /api/recording`   | Interview answer analysis (STAR, pacing, fillers)           |
| `GET /api/health`       | Liveness + DB presence                                      |

## Layout

- `src/lib/api.ts` — typed client + status→badge mapping
- `src/lib/useAsync.ts` — tiny fetch-on-mount hook (no react-query needed)
- `src/components/ui/*` — shadcn primitives (card, badge, button, table, input, textarea)
- `src/components/*` — dashboard blocks (KpiCard, PipelineFunnel, FieldMix, ErrorNote, tables, header) + one component per page
- `src/index.css` — Job Bot design tokens ported to shadcn's CSS-variable contract

## Production build

```bash
npm run build      # → web/dist (static). Serve behind the same origin as the API
                   #   and drop the CORS allow-list in job_bot/api.py.
```
