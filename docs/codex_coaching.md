# Separate career coach alongside Codex

The Orca launcher starts a backend terminal and an independent Claude Code
terminal. They share the Job Bot checkout, database, profile, and coaching files.
The same separation can be kept while engineering happens in Codex.

## Keep Claude as the coach

Open a terminal in the Job Bot checkout and run:

```powershell
.\scripts\career-coach.cmd
```

This starts the installed Claude Code CLI with the coaching brief and resume
instructions already provided by the launcher. It does not require Orca and does
not start the backend, pull git changes, or run job discovery. Claude Code's own
account and login remain separate from the dashboard's Anthropic API key.

Use the Codex engineering task for code changes, tests, and troubleshooting.
Use the coach terminal for search strategy, reviewing opportunities, interview
practice, and deciding the next application action. Both read the same files.

## Use a dedicated Codex coach instead

Create a separate task in the saved Job Bot project and ask for coaching mode.
The primary checkout is simplest for personal local files; if a worktree is used,
read the private coaching files from `config.DATA_HOME` as described in AGENTS.md.
An example starting prompt:

> Act as my career coach. Read AGENTS.md, COACH.md, and COACH_STATE.md; run
> `py -3 coach_snapshot.py .`. Check freshness and missing-data warnings first.
> Resume my existing decisions and unfinished agenda without making me repeat
> them. Give me one concrete next action. Keep engineering work in the other task.

A separate Codex task is not a Claude session. Choose the interface intentionally;
the shared context does not make the model providers interchangeable.

## Shared facts and memory

- `COACH.md`: coaching tone and data sources.
- `COACH_STATE.md`: decisions, corrections, and unfinished actions. The active
  coach maintains it after substantive discussions. Before saving, reread the
  file and merge changes; don't overwrite another session's newer decisions.
  Engineering sessions should record technical work in the private review and
  leave ownership of the coaching agenda to the active coach.
- `data/master_profile.json`: source profile used by generation and scoring.
- `data/job_bot.db`: recorded jobs, applications, interviews, and correspondence.
- `coach_snapshot.py`: shared read-only snapshot with source freshness, recent
  recruiter mail, older correspondence, likely acknowledgements, and growth hints.

Private memory and data are gitignored. Dated counts or job-board claims inside
memory must be rechecked, not repeated as current facts. The plugin's separately
bundled snapshot can lag behind this repository; use the repository CLI here.

The dashboard coach now reads shared memory but cannot update it or send mail.
Its chat history currently lasts only while the Coach component stays mounted.
Use the separate CLI/task for an ongoing relationship until durable dashboard
history and reviewed memory updates are implemented.

## Next improvements, in order

1. Restore Google access using **Reconnect Google**, then verify a successful
   sync. Local code cannot complete Google's account-consent interaction for you.
2. Add a small action list with source links, due dates, and completion evidence.
   Let the coach identify one next action and carry it to the following session.
3. Support employer-specific application tracks and validate graduation facts
   before generating documents. Do not globally overwrite a graduation date.
4. Add a Find Jobs-to-tracker handoff that distinguishes saved jobs from submitted
   applications. Evaluate applications and progress, not just discovery volume.
5. Persist dashboard chat and add an explicit review step for saving new decisions
   to coaching memory. Keep one writer responsible for the agenda at a time.
