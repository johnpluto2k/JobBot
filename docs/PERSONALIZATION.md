# Making Job Bot yours

Three layers. The first is private and never leaves your machine. The second is
generic and reads the first. The third still carries the original owner's field
(accounting, audit, IT risk, the DC-Maryland-Virginia market) and is where you
spend an hour if your search looks different.

## 1. Your data (gitignored, never committed)

| Path | What it holds | Created by |
| --- | --- | --- |
| `.env` | API keys, Google OAuth client, home-region markers | you, from `.env.example` |
| `documents/` | résumés, cover letters, transcripts, project write-ups | you |
| `data/master_profile.json` | the structured profile everything reads | `python -m job_bot.build_profile` |
| `data/job_bot.db` | applications, companies, emails, interviews, outreach, offers | the app |
| `data/affiliations.json` | relationship tag → "as a fellow …" phrase for outreach | you (optional) |
| `data/google_token.json`, `data/gmail_sync_status.json` | Google refresh token and sync state | sign-in |
| `COACH.md` | the coach's brief about you and its tone | you, from `templates/COACH.template.md` |
| `COACH_STATE.md` | the coach's running memory | the coach, from `templates/COACH_STATE.template.md` |
| `inputs/`, `Resumes/`, `CoverLetter/`, `resume-studio/` | raw source folders | you |

If you use git worktrees, `data/` and the coaching files live in the primary
checkout; `config.DATA_HOME` resolves there from any worktree.

## 2. Generic code that reads your data

`job_bot/candidate.py` is the one place identity comes from. It reads
`personal.name`, `education[0]` (school, major, secondary major, graduation
date), and `targets.target_roles` from the profile, with `JOB_BOT_CANDIDATE_NAME`
and `JOB_BOT_CANDIDATE_BLURB` as fallbacks before a profile exists, and neutral
wording ("the candidate", "a job seeker") after that. Every prompt, letter,
sign-off, LinkedIn headline, mock-interview persona, and coach system prompt
goes through it. If a generated document names the wrong person, fix the
profile, not the code.

`job_bot/outreach.py` builds its self-introduction from the profile and looks
up shared-background phrases by relationship tag: `alum` and `school` are
derived from your school; anything else comes from `data/affiliations.json`.

`job_bot/watch.py` takes its home region from `JOB_BOT_HOME_MARKERS`.

Launcher scripts (`start-job-bot.cmd`, `scripts/*.cmd`, `scripts/*.ps1`)
locate the repo from their own path.

## 3. Still tuned to the original owner's field

In rough order of how much they shape what you see:

| File | What's specific | What to do |
| --- | --- | --- |
| `job_bot/newgrad.py` | `INTERNSHIP_QUERIES`, `FULLTIME_QUERIES`, `TRACKS` (Accounting & Audit, Finance & FP&A, Data & Analytics, IT & Cybersecurity, Software & Engineering), hiring cycles derived from a graduation date | Rewrite the query lists and track names for your roles. This drives the Find Jobs page. |
| `job_bot/skills_ontology.py` | canonical skills, synonyms, role families, market and company signals used by the ATS scorer and growth plan | Add your field's skills and role titles; the scorer only credits what it knows. |
| `job_bot/applications.py` `_FIELD_SIGNALS` | maps job titles to career fields for the funnel's field mix | Add your fields' title patterns. |
| `job_bot/portals.py` `DEFAULT_KEYWORDS`, `_SENIOR_RE` | title keywords the watcher and portal scan keep | Replace with titles you'd apply to. |
| `job_bot/watch_registry.py` | 88 verified company job-board endpoints, mostly Big 4, GRC-tech, govcon, DMV employers | Keep what overlaps; add yours only after verifying the endpoint live. |
| `scripts/seed_broad_targets.py` | ~150 target companies with tiers and fields | Replace the list before running. |
| `job_bot/company_research.py` `FIRM_KB` | curated hiring-process intel for Big 4 and a few others | Add entries for your target firms or rely on `--news`. |
| `job_bot/offers.py` `COL_INDEX`, `job_bot/salary.py` `ROLE_BASELINES` | cost-of-living indices and salary baselines weighted to the DC area and entry-level finance | Extend the tables for your cities and level. |
| `job_bot/connections.py` `RELATIONSHIP_WARMTH` | warmth per relationship tag (`umd`, `pse`, `iefs` are the original owner's orgs) | Add your tags; unknown tags default to first-degree warmth. |
| `web/src/components/NetworkTab.tsx` | display labels for those same tags | Add labels for your tags. |
| `job_bot/cover_letter.py`, `job_bot/cover_ab.py`, `job_bot/thankyou.py` | template sentences use audit / controls / analytics vocabulary; the CPA line appears only when the major contains "account" | Edit the template paragraphs to your field's language. With an API key the LLM path rewrites them from the JD anyway. |
| `job_bot/interview.py`, `job_bot/questions.py`, `job_bot/story_bank.py` | firm personas (`big4`, `ib`, `tech`, `fintech`) and a question bank leaning to audit and finance | Add personas and questions for your interviews. |
| `job_bot/transcript.py` | parses one university's unofficial transcript format | Only matters if you use `--transcript`; write a parser for yours or skip it. |
| `job_bot/routing.py` | portal notes mention Handshake as critical for students | Harmless; edit if you like. |
| `docs/resume_branding_playbook.md`, `docs/resume_track_contract.md`, `docs/prompts/` | the original owner's résumé positioning and past prompts | Read as examples; write your own playbook. |
| `.claude/agents/recruiter-reviewer.md` | reviews against "Big 4 audit/advisory and tech/data" hiring norms | Adjust the persona to your industry. |

## What is deliberately not personal

- The funnel logic, dedup rules, and status-update safety in `applications.py`
  and `inbox.py`.
- The read-only coach snapshot and its freshness handling.
- The Gmail classification pipeline (categories are generic: interview invite,
  assessment, offer, rejection, recruiter reply, noise).
- The React dashboard and API.
- The watcher's fetchers for Greenhouse, Ashby, SmartRecruiters, and Workday.
