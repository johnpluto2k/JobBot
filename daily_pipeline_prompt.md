You're running the daily Job Bot pipeline unattended. Work through these steps
in order, using the job-scout, resume-tailor, outreach-drafter, inbox-triager,
and growth-planner subagents rather than doing the work yourself directly.
Delegation is one level deep: you (the conductor) call each subagent; subagents
never call other subagents. Every delegated step must come back with evidence
(counts, ATS scores, file paths, error text) — if a subagent reports "done" with
no evidence, re-run it.

1. Delegate to job-scout: find new postings. Expect back: how many new postings
   saved, how many are high-priority/on-target, and any scrape errors.

2. If job-scout reports any new high-priority, on-target postings, delegate to
   resume-tailor for the **top 3 at most**. Feed it those specific postings.
   Expect back: before/after ATS score and the output path
   (`data/applications/<slug>/`) for each package.

3. Delegate to outreach-drafter for any follow-ups that are now due
   (job_bot.applications / outreach.followup_date <= today) — **drafts only**.
   Expect back: what was drafted (status='drafted') and who John must review/send
   manually.

3.5. Delegate to inbox-triager: classify unhandled recruiter email
   (`tracked_emails` where handled = 0) into live opportunity / scheduling request
   / rejection / noise — **read-only, never send/reply/archive**. Expect back: the
   live opportunities and scheduling requests that need John's action, plus bare
   counts of rejections/noise. Anything time-sensitive here (an interview invite,
   a scheduling request with a near deadline) is URGENT — carry it to the top of
   the log.

4. Delegate to growth-planner to refresh insights. Expect back: only what's new or
   changed in the growth plan since last time.

5. Write a short summary (not a full data dump) to
   `data/daily_pipeline_log/<YYYY-MM-DD>.md`: what ran, what's new, and — in a
   clearly-marked **"Needs John's attention"** section at the top — anything
   urgent: interview invites or scheduling requests from inbox-triager, drafts to
   review, follow-ups to send, and anything that errored. This log is what the
   career-coach skill / CLAUDE.md coaching mode references when John asks "what
   happened while I was away," so lead with the time-sensitive items.

6. **File the Agent HQ report** (John's Obsidian dashboard). Do this yourself
   (conductor), last, even if earlier steps failed — a failure report is still a
   report:
   - Write `C:\ClaudeProjects\ObsidianVault\Reports\<YYYY-MM-DD> Job Bot.md`
     (overwrite if re-run same day) in exactly this shape — short, no data dump:

     ```markdown
     # Job Bot — <YYYY-MM-DD>

     **Result:** ✅ ran clean | ⚠️ needs attention | ❌ errored
     **Needs John:** no — nothing to review  *(or: yes — one bullet per item)*

     - Postings: <new> new, <high> high-priority
     - Resumes tailored: <n> · Drafts awaiting review: <n>
     - Inbox: <live> live opportunities, <sched> scheduling requests

     Full log: `data/daily_pipeline_log/<YYYY-MM-DD>.md` · Dashboard: [[Agent HQ]]

     #report #job-bot
     ```

   - Then update the **Job Bot row only** of the "Team status" table in
     `C:\ClaudeProjects\ObsidianVault\1 Projects\Agent HQ.md` to
     `| Job Bot | <YYYY-MM-DD> | ✅/⚠️/❌ <three-word summary> | yes/no |`.
     Touch nothing else in that file.
   - If the vault isn't writable for any reason, note that at the top of the
     daily pipeline log and finish normally — never let reporting block the run.

7. **Sync the Obsidian vault** (conductor, right after the Agent HQ report; same
   rule — if the vault isn't writable, note it in the log and finish normally):

   a. **Daily note — Pipeline section.** Open
      `C:\ClaudeProjects\ObsidianVault\Daily Notes\<YYYY-MM-DD>.md`. If it
      doesn't exist, create it from
      `C:\ClaudeProjects\ObsidianVault\Templates\Daily Note.md` (replace
      `{{date}}` with today's date). Under the `## Pipeline` heading, replace
      the placeholder bullet with a condensed digest — bullets only, no data
      dump:
      - new high-priority jobs (count + company/title for each),
      - drafts awaiting John's review,
      - urgent recruiter email (interview invites / scheduling requests from
        inbox-triager),
      - upcoming interviews.
      If a re-run same day, overwrite the Pipeline section's bullets, not the
      rest of the note. Leave every other section untouched.

   b. **Rolling funnel snapshot.** Run `python3 coach_snapshot.py .` and
      **overwrite** (full rewrite, newest data only)
      `C:\ClaudeProjects\ObsidianVault\2 Areas\Job Search Pipeline Status.md`
      with this shape:

      ```markdown
      # Job Search Pipeline Status 🎯

      *Auto-written by Job Bot's daily run — last updated <YYYY-MM-DD>. Don't edit by hand.*
      Back to [[Job Search]] · today's detail: [[<YYYY-MM-DD>]]

      ## Funnel (canonical, from applications.summary())
      | Stage | Count |
      |-------|-------|
      | In review | <n> |
      | Interviewing | <n> |
      | Offers | <n> |
      | Rejected | <n> |
      | Ghosted | <n> |

      Response rate: <x>% · Interview rate: <x>%

      ## Time-sensitive
      - <upcoming interviews, overdue follow-ups, unhandled recruiter email — or "nothing pending">

      ## Focus (from growth plan)
      - <current focus, one or two bullets>

      #job-search
      ```

## How the agents cooperate on a daily run

- job-scout's high-priority finds **feed** resume-tailor (top 3 max).
- resume-tailor's completed packages **trigger** outreach-drafter for any due
  follow-ups tied to those applications.
- inbox-triager's action-worthy findings **and** growth-planner's delta both
  **land in** the single `data/daily_pipeline_log/<date>.md` that coaching mode
  reads.

## Hard safety lines (never cross, even if a capable tool exists)

- **Never send outreach messages.** Drafts only, status='drafted'.
- **Never submit applications.** `submit=False` stays; never override it.
- **Never edit `data/master_profile.json`.** If something seems to need a profile
  change, flag it in the log instead of making it.
- **inbox-triager is read-only** — never send, reply to, archive, or mark email
  handled.
