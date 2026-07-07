# Prompt: Add a personal section + avatar corner to the Job Bot dashboard

Paste this into a Claude/Cowork session with access to the `Job Bot` folder to implement it.

## Context

- App: Streamlit dashboard in `job_bot/dashboard.py`, styled by the design system in `job_bot/ui.py` (Inter font, accent `#4F46E5`, card/hero components defined as HTML-returning functions).
- Persistent header lives in `dashboard.py` lines ~61–65 (`st.markdown("# Job Bot")` + caption with name/email/location) — shows on every tab.
- A second, tab-scoped greeting banner is built by `ui.hero()` (`ui.py` line 232) and rendered inside the "Action Center" tab (`dashboard.py` ~line 114).
- Profile data already loads from `profile.json` into `profile["personal"]` (name, email, location) — see `dashboard.py` line 60.
- An "Overview" tab already has a "Profile" section (`dashboard.py` ~line 312) showing education, skills, certifications.
- No real photo file exists yet — the LinkedIn data export only contains CSVs, not the profile picture. Build for a placeholder now (initials avatar) with an easy swap-in point for a real image later (e.g. a `profile_photo_url` or local file path in config/profile.json that falls back to initials if absent).

## What to build

1. **Avatar component** in `ui.py`: a function like `avatar(name: str, image_url: str | None = None, size: int = 40) -> str` that renders a circular image if a URL/path is given, otherwise a circle with initials on an accent gradient (`--jb-accent` → `--jb-accent-2`), matching the existing rounded/soft-shadow style used elsewhere in the file.

2. **Corner placement**: pin the avatar to the top-right of the persistent header (the always-visible header at `dashboard.py` lines 61–65), not just inside one tab. Add the CSS/markup needed so it sits in the corner without disrupting the existing title/caption layout.

3. **Personal section**: expand the existing "Profile" block in the Overview tab (`dashboard.py` ~line 312) into a proper personal-info card: name, headline/target role, location, LinkedIn URL, email — styled consistently with the other cards in `ui.py` (rounded border, `--jb-line`, hover lift). Pull values from `profile["personal"]` where they exist; leave graceful blanks for missing fields.

4. **Fallback behavior**: if no photo is configured, initials avatar must render cleanly everywhere the avatar is used — no broken image icons, no layout shift once a real photo is added later.

## Constraints

- Match the existing design system exactly (fonts, colors, spacing, animation classes like `jb-anim`) — don't introduce a new visual style.
- No new dependencies; keep using Streamlit's `st.markdown(..., unsafe_allow_html=True)` pattern already used throughout `ui.py`.
- Don't break the existing tabs, KPI grid, or hero banner.

## Acceptance check

- Run the app (`streamlit run` per README) and confirm: avatar shows in the header corner with initials, Overview tab shows the new personal card, nothing else visually regresses.
