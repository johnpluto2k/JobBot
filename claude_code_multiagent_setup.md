# Prompt/setup: multi-agent, mostly-autonomous Job Bot pipeline in Claude Code

Paste the plan below to Claude Code (or apply the file changes yourself) from the `Job Bot` repo root. This sets up real Claude Code features — not a metaphor — so read the "what these actually are" section before wiring it up.

## What Claude Code actually offers here (so we're not overpromising)

Two real, separate mechanisms, used together:

- **Subagents** (`.claude/agents/*.md`): specialized child agents the main Claude Code session can delegate to. Each gets its own context window and a `tools:` allowlist (if you don't set one, it inherits everything). They run to completion and hand a summary back to whoever called them. There's no confirmed support for a subagent calling another subagent — keep the chain one level deep (main session → subagent), not nested.
- **Headless mode** (`claude -p "prompt"`): runs Claude Code non-interactively, scriptable, pipeable, schedulable via cron / Windows Task Scheduler. This is the actual "works on its own" mechanism — subagents alone still need you to open a session and ask.

There's no built-in auto-orchestrator that decides what to run next on its own — you write one prompt that calls the subagents in sequence, and a scheduler calls *that* prompt. (Claude Code also has an experimental "Agent Teams" mode for independent, peer-messaging sessions — overkill for this pipeline; skip it.)

## Safety defaults built into this setup

- **Outreach messages are drafted, never sent** — this is already structurally true today: `outreach.py` only has drafting functions (`draft`, `follow_up`, `referral_request`, `networking_intro`); there's no send integration in this codebase at all. The orchestrator prompt below still says it explicitly, so it stays true if send capability is ever added later.
- **Applications are never auto-submitted** — already true in `autofill.py` (`submit=False` by default); the orchestrator never overrides this.
- Start with `claude -p` **without** `--dangerously-skip-permissions` for the first week or two and watch what it actually does before removing the safety net. The `tools:` allowlist on each subagent (below) is the durable safety mechanism, not the permission flag.

## 1. Create the subagents

`.claude/agents/job-scout.md`:
```markdown
---
name: job-scout
description: Searches job boards and refreshes the pipeline. Use for "find new jobs", "scan for postings", "run the daily job search."
tools: Bash, Read, Grep
---
Run the job search phase only. Use `python -m job_bot.newgrad` (or `job_bot.search_jobs`)
against John's target tracks. Score, route, and save to `data/job_bot.db` as the
existing pipeline already does — don't change scoring logic, just run it.
Prefer Indeed by default; only hit LinkedIn/Glassdoor if explicitly asked, per the
existing scraping-risk guidance (LinkedIn throttles ~page 10/IP). Report back: how
many new postings saved, how many are high-priority/on-target, and any scrape
errors — don't dump the full listing, the parent agent will decide what to do next.
```

`.claude/agents/resume-tailor.md`:
```markdown
---
name: resume-tailor
description: Generates a tailored resume + cover letter package for a specific job posting. Use for "tailor a resume for X", "generate an application package."
tools: Bash, Read, Write, Edit
---
Run `python -m job_bot.generate` for the job(s) you're given (by URL, file, or
DB row). Never invent experience — the existing tailoring logic already enforces
this; your job is just to run it correctly and report the before/after ATS score
and where the output landed (`data/applications/<slug>/`). If asked to do this for
multiple postings, do the highest-priority ones first and stop if more than
~5 packages would be generated in one run — flag that back instead of silently
burning API cost on a long tail of low-priority postings.
```

`.claude/agents/outreach-drafter.md`:
```markdown
---
name: outreach-drafter
description: Drafts (never sends) follow-up, referral, or networking messages. Use for "draft a follow-up to X", "write a referral request."
tools: Bash, Read
---
Use `job_bot.outreach` to draft messages (follow_up / referral_request /
networking_intro). These are drafts only — there is no send capability in this
codebase and this agent must never be asked to actually send anything (email,
LinkedIn, or otherwise), even if a send-capable tool is available in the
environment. Save drafts with status='drafted' as the existing schema already
expects; report what was drafted and who needs to review/send it manually.
```

`.claude/agents/growth-planner.md`:
```markdown
---
name: growth-planner
description: Refreshes the growth plan (skill gaps, certs, portfolio projects) from the live profile + application history. Use for "update my growth plan", "what should I be building toward."
tools: Bash, Read
---
Run `python -m job_bot.growth` (or call `job_bot.growth.build_plan()`) and report
the insights and focus-field changes since last time — only what's new or
changed, not the full plan every time.
```

## 2. The daily orchestrator prompt

Save as `daily_pipeline_prompt.md` at the repo root — this is what gets run headlessly, not a subagent itself:

```
You're running the daily Job Bot pipeline unattended. Work through these steps
in order, using the job-scout, resume-tailor, outreach-drafter, and
growth-planner subagents rather than doing the work yourself directly:

1. Delegate to job-scout: find new postings.
2. If job-scout reports any new high-priority, on-target postings, delegate to
   resume-tailor for the top 3 at most.
3. Delegate to outreach-drafter for any follow-ups that are now due
   (job_bot.applications / outreach.followup_date <= today) — drafts only.
4. Delegate to growth-planner to refresh insights.
5. Write a short summary (not a full data dump) to
   data/daily_pipeline_log/<YYYY-MM-DD>.md: what ran, what's new, what needs
   John's attention (drafts to review, follow-ups to send, anything that
   errored). This log is what the career-coach skill / CLAUDE.md coaching mode
   should reference when John asks "what happened while I was away."

Never send outreach messages, never submit applications, never edit
master_profile.json — flag anything that seems to need a profile change instead
of making it.
```

## 3. Schedule it (Windows Task Scheduler)

Create a basic task that runs daily, e.g. 7am:
```
Program/script:  claude
Arguments:       -p "$(Get-Content 'C:\ClaudeProjects\Job Bot\daily_pipeline_prompt.md' -Raw)" --output-format json
Start in:        C:\ClaudeProjects\Job Bot
```
(Wrap in a small `.ps1` or `.bat` if Task Scheduler's argument handling gets fussy with the file-read.) Leave `--dangerously-skip-permissions` off at first — you'll get prompted the first few runs, which is exactly how you confirm it's only doing what the subagent files say before trusting it fully unattended.

## Acceptance check

Run `daily_pipeline_prompt.md` manually via `claude -p` once first (not yet scheduled), confirm each subagent gets invoked in order, confirm a log file appears under `data/daily_pipeline_log/`, and confirm no outreach draft gets marked/sent and no application gets submitted. Only add the Task Scheduler entry once a manual run looks right.
