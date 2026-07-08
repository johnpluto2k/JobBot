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
