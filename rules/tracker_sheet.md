# The tracker sheet

Every application is one row in the owner's Google Sheet. The sheet is the
record of the search; there is no database. The owner's sheet link and id are
in `coach/tracker.md`.

## Layout

The sheet is made from `templates/tracker_template.xlsx`. Three tabs.

**Tracker**

- Rows 3 to 13 hold summary boxes that calculate themselves: status counts
  (A6:B13), At a Glance (D3:E7), By Track (H3:I11). Never type in them.
- **Row 15 is the header. Data starts at row 16.**

| Col | Header | What goes in it |
|---|---|---|
| A | Company | Employer name, spelled the same way every time |
| B | Position | Title as posted, with city if the same title is posted in several |
| C | Date Applied | The day the owner submitted, as a date |
| D | Application Status | Dropdown: Submitted, In Progress, Interviewing, Offer, Rejected, Ghosted, Withdrawn |
| E | Details | Requisition number, what was uploaded, referral, dated notes, separated by " · " |
| F | Applicant Portal | Link to the posting or the portal |
| G | Cold Apply | Yes when there was no referral or contact, otherwise No |
| H | Location | City and state |
| I | Salary (posted) | As the posting states it, or "not posted" |
| J | Work Mode | Onsite, Hybrid or Remote, with detail if given |
| K | Grad Date Used | The graduation or start date on this application. Leave blank if it doesn't apply |
| L | Deadline | Date, "Rolling", or blank |
| M | Track | Dropdown fed by the Setup tab |

Statuses: **Submitted** means sent and nothing heard. **In Progress** means
started or built but not yet sent. **Ghosted** is the owner's call, usually
after several weeks of silence. **Withdrawn** means the owner pulled out.

**Outreach**: header in row 1, one row per person: Contact, Company, Email,
LinkedIn, Email source, Email verification, Target role / requisition, Status
(Planned, Drafted, Sent, Replied, Follow-up due, Closed), Planned send date,
Sent date, Follow-up date, Subject, Email draft, Reply / outcome, Next action,
Notes. Drafted is never Sent; only the owner sends.

**Setup**: the lists behind the dropdowns. Tracks are in A2:A9; the owner picks
them during setup. Leave the status list alone.

## Reading

Use the Google Drive connector to read the sheet by its id. Read it at the
start of any check-in and again after any write.

Work out from the rows, not from memory:

- counts by status and by track (the summary boxes give the same numbers)
- applications in the last 7 and 14 days, and the date of the last one
- deadlines in column L within the next 7 days on rows still In Progress
- rows still Submitted after 21 days: candidates for a follow-up or Ghosted,
  the owner decides
- Outreach rows whose follow-up date has passed

If the connector can't open the sheet, say so. Don't guess, and don't coach
from an old read.

## Writing

The Drive connector reads sheets but does not edit cells. Writes go through
**Claude in Chrome**, in the Chrome profile signed in to the Google account
that owns the sheet.

**Add a row only after the owner says they submitted** (or asks for an In
Progress row). Change a status only when the owner tells you or you can show
them the email that says so.

The method that works:

1. Read the sheet through Drive and find the first empty row, N.
2. Open the sheet in a **new tab**. Don't use or close the owner's other tabs.
3. Click the Name box (top left, shows the current cell), type `A<N>`, press
   Enter. Take a screenshot and confirm the Name box shows `A<N>`.
4. Type one cell, press **Tab**, type the next. One cell at a time: a whole row
   typed as one tab-separated string lands in a single cell.
5. Send keys one per action. A string of several key names, or a repeat count,
   can fire only once in Sheets.
6. If Sheets offers an autocomplete suggestion you don't want, press Delete
   before Tab.
7. Dates as `M/D/YYYY`. For dropdown columns type the exact option text.
8. Finish the row with Tab, not Enter on an empty row.
9. Read the sheet through Drive again and check every cell of the new row. If
   something landed in the wrong place, undo with Ctrl+Z (Cmd+Z on a Mac) and
   redo it; never leave a half-written row.

For one status change: Name box, type the cell (for example `D23`), Enter, type
the new status, Enter, then re-read.

If the browser is unavailable or a write keeps failing, hand the owner the row
as a list of column and value and ask them to paste it. Don't keep retrying.

## Don't

- Don't touch anything above row 15 on the Tracker tab.
- Don't sort, filter, insert or delete rows, or change the header.
- Don't change sharing on the sheet.
- Don't log a posting the owner hasn't applied to. A lead is not an
  application.
- If the owner keeps their own notes in the sheet (some people keep private
  things in a tracker), don't read them out, copy them, or move them.
