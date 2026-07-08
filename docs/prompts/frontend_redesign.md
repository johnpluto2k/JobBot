# Prompt: finish + redesign the React front end (web/) — minimalist, clear actions

Paste into Claude Code from the repo root.

## Reality check before redesigning: this is mid-migration, not finished

Worth being precise about what's actually wrong, since the underlying design system (`web/src/index.css` tokens, the shadcn `ui/` components, Tailwind v4) is already solid — Inter type, indigo accent, hairline borders, consistent card/button/badge primitives. The "horrible" feeling is coming from the app being in a half-finished migration state, confirmed by reading the code and the root `README.md`'s own "IN PROGRESS" section:

- `App.tsx` still uses a **12-item horizontally-scrolling tab strip** (Overview, Coach, Applications, Pipeline, Find Jobs, Network, Growth, Offers, Score a JD, Company Brief, LinkedIn, Interview Lab) — the README already flags this as the "swipe bar" to be replaced with a sidebar, and says explicitly that work was never done.
- **Resume Studio isn't mounted anywhere.** `ResumeStudioTab.tsx` exists and is fully built, but `App.tsx` never imports or renders it — there's no tab/page for it at all right now. It's a finished feature that's currently invisible.
- `FindJobsTab.tsx` is missing the job-board site picker even though the backend already supports it (`SearchRequest.sites`, `/api/cycles` already returns `sites`/`default_sites`) — the Streamlit side has this, the React side doesn't yet.
- There's no consistent "primary action" placement pattern across pages — each tab buries its main button (Search job boards, Render PDF, etc.) inside a form row rather than treating it as *the* thing this page does.

Fix the structural gaps first (they're most of "horrible"), then do the minimalism/action-button pass on top.

## 1. Replace the tab strip with a sidebar (the README's own "main ask", finish it)

In `App.tsx`: replace the `<Tabs>`/`<TabsList>` horizontal strip with a left sidebar — icon + label per item, active-state highlight, using the existing `--primary`/`--accent` tokens (don't invent new colors). Group the now-13 destinations (12 existing + Resume Studio) into sections instead of one flat list, e.g.:
- **Overview** — Overview, Coach
- **Pipeline** — Applications, Pipeline, Find Jobs
- **Build** — Resume Studio, Score a JD, LinkedIn
- **Network & Growth** — Network, Growth, Offers, Company Brief, Interview Lab

Keep routing state-based (`useState` + `localStorage` for the active page, as the README already specified) rather than pulling in a router dependency — this is a single-page dashboard, not a multi-route site. Collapse the sidebar to a drawer (hamburger toggle) below a `md` breakpoint; the content area keeps the existing `mx-auto max-w-6xl` treatment.

Mount `<ResumeStudioTab />` in the new "Build" section — it's fully built, it's just been unreachable.

## 2. Finish `FindJobsTab.tsx`'s site picker

Add a job-board multiselect (badge-toggle style, matching the existing "Career tracks" badges in the same file) seeded from `cycles.default_sites`, plus a results-per-role slider (5–50, the backend already supports up to 50). Pass `sites`/`results_per` into `api.search(...)`. Update the "Live-scrapes Indeed and scores each posting" copy to reflect the actual selection instead of a hardcoded "Indeed." Disable the Search button when zero sites are selected, same as it's already disabled when zero tracks are selected.

## 3. Establish one consistent action-button pattern

Right now every page's primary button (`Search job boards`, `Render PDF`, etc.) is default-variant and placed wherever it fell in the form layout — fine individually, inconsistent as a whole. Standardize:
- **One primary action per page**, always the `default` Button variant, always at the bottom-right of its containing `Card` (or a sticky bar at the bottom of the card on longer forms) — not inline mid-row with other controls.
- **Secondary/utility actions** (downloads, external links, "open in typst.app", etc.) always `outline` or `ghost` variant, or icon-only with `aria-label` where space is tight (the `JobsTable`'s external-link icon is already a good example of this — replicate that restraint elsewhere instead of full buttons for secondary actions).
- Loading state on the primary button always follows the `FindJobsTab` pattern already in place (`Loader2` spin + verb-ing label, e.g. "Searching…") — apply the same to Resume Studio's render button and anywhere else a long-running action exists.

## 4. Minimalism pass

- Audit KPI-card density per page — `Overview` and `FindJobsTab` both show a 4-card KPI grid immediately above their main content; keep that pattern (it's good), but don't let any single page show more than one KPI grid + one primary content block without a clear section break (`ui/card` `CardHeader`/`CardTitle`, already used correctly in `FindJobsTab`).
- Reuse the existing `ErrorNote`-style and skeleton-loading patterns from `App.tsx` consistently across every tab component instead of ad hoc `<p className="text-destructive">` one-offs (a couple of components — check `FindJobsTab`'s inline error `<p>` — should switch to the shared pattern).
- Tables (`JobsTable`, `ApplicationsTable`): keep them as-is structurally (they're already clean — hairline rows, right-aligned numerics, restrained badges) but confirm no table ever needs horizontal scroll on a standard laptop width now that the sidebar is eating some width; trim a column (e.g. combine Location into the Company cell as a subline) if it does.

## Acceptance check

`cd web && npm run build` (tsc must pass clean), then `uvicorn job_bot.api:app --port 8000` + `npm run dev` and eyeball: sidebar renders and collapses to a drawer on a narrow viewport, Resume Studio is reachable from nav, Find Jobs has a working site picker, and every page has exactly one clearly primary button. Compare against the Streamlit dashboard's equivalent pages for parity — nothing that exists there should have quietly disappeared in React.
