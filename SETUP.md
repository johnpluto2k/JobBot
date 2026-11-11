# Setup

About 20 minutes, most of it signing in to things. After step 3 the coach
takes over and walks you through the rest in plain conversation.

**Before you start, you need**

- A paid Claude plan (Pro, Max, Team or Enterprise). The free plan does not
  include Claude Code, the program the coach runs in.
- A Google account, for your tracker sheet.
- Google Chrome or Microsoft Edge.

## 1. Download the project

On the project's GitHub page click the green **Code** button, then **Download
ZIP**. Unzip it somewhere you'll find it again, such as your Documents folder.

## 2. Double-click Start Coach

Open the folder and double-click:

- **Start Coach - Windows** on Windows
- **Start Coach - Mac** on a Mac

A window opens and checks what you have. If Claude Code or Python is missing
it asks before installing each one. Then it opens two pages in your browser:

1. **Claude connectors.** Add **Google Drive** and sign in with the Google
   account you want your tracker sheet in. This lets the coach read the sheet.
   (Optional: add **Gmail** too, so the coach can check for recruiter replies.
   It only reads mail; it never sends.)
2. **The Claude extension for Chrome.** Click **Add to Chrome** and sign in
   with your Claude account. This lets the coach add rows to your sheet and
   work in Overleaf.

Go back to the window and press Enter.

> **If your computer asks whether you're sure about opening the file**, that is
> normal for a script downloaded from the internet. On Windows choose **More
> info**, then **Run anyway**. On a Mac, right-click the file and choose
> **Open**; if that is refused, open System Settings, Privacy & Security, and
> click **Open Anyway**. Or skip the double-click and use the commands in
> "Doing it by hand" below.

## 3. Sign in and say hello

The first time, Claude Code opens your browser to sign in. After that the
coach starts setup on its own. If it is waiting for you, type:

```
set me up
```

## 4. What the coach does next

It asks before each step and waits for you.

1. **Checks your tools** and tells you plainly if something isn't connected.
2. **Creates your tracker.** A Google Sheet called "Job Tracker" appears in
   your Drive.
3. **Asks for your documents.** Put everything you have into the `documents`
   folder: every resume version, cover letters, transcripts, project
   write-ups, your LinkedIn connections export. Don't tidy it first.
4. **Writes your profile** and asks you about anything that doesn't add up.
5. **Asks what you're aiming for:** kinds of role, locations, employers, how
   many applications a week.
6. **Builds your master resume**, a multi-page file with everything you've
   ever done. You'll make a free account at
   [overleaf.com](https://www.overleaf.com/register) and a blank project
   called "Master Resume"; the coach puts the resume in it.

## 5. Every day after that

Double-click **Start Coach** again. It opens your tracker sheet and the coach,
which tells you where things stand.

If you use the Orca app and this folder is open in it, the coach opens as a
"Career Coach" tab there. If you don't, it opens in its own window. There is
nothing to set up either way.

| You say | The coach does |
|---|---|
| "Tailor an application for this posting:" and paste the link | Builds a one-page resume and cover letter in `applications` |
| "I submitted the Northwind one" | Adds the row to your sheet |
| "Where are we?" | Reads the sheet and tells you what needs attention |
| "Northwind rejected me" | Updates that row |
| "Write a note for this person" (with their LinkedIn profile open) | Drafts a connection note for you to send |
| "Find new postings" | Returns a short list, newest first |

You always press Send and Submit yourself. The coach never does.

## Your files stay yours

Everything you put in `documents`, and everything the coach writes in
`resume`, `applications` and `coach`, stays on your computer. Those folders
are excluded from Git, so they are never uploaded with the project. Your sheet
lives in your own Google Drive.

---

## Doing it by hand

If you'd rather type the commands, or the launcher didn't work. Use
**Terminal** on a Mac (Cmd+Space, type "Terminal") and **PowerShell** on
Windows (Windows key, type "PowerShell").

**Install Claude Code**

| Mac | Windows |
|---|---|
| `curl -fsSL https://claude.ai/install.sh \| bash` | `irm https://claude.ai/install.ps1 \| iex` |

Open a new window and check: `claude --version`

**Install Python** (3.10 or newer; used to measure your resume PDF)

| | Mac | Windows |
|---|---|---|
| Check | `python3 --version` | `python --version` |
| Install | [python.org/downloads](https://www.python.org/downloads/) | `winget install -e --id Python.Python.3.13` or [python.org/downloads](https://www.python.org/downloads/) |

**Get the project with Git instead of a ZIP** (makes updates easier)

```
git clone https://github.com/johnpluto2k/JobBot.git
```

**Go into the folder and install the one Python package**

| Mac | Windows |
|---|---|
| `cd ~/Documents/JobBot` | `cd $HOME\Documents\JobBot` |
| `python3 -m pip install -r tools/requirements.txt` | `python -m pip install -r tools\requirements.txt` |

**Connect Google Drive:** [claude.ai/customize/connectors](https://claude.ai/customize/connectors)

**Install the Chrome extension:** [Chrome Web Store](https://chromewebstore.google.com/detail/claude/fcoeoabgfenejglbffodgkkbkcdhcgfn)

**Start the coach**

```
claude --chrome
```

then type `set me up`.

## If something goes wrong

| Problem | Fix |
|---|---|
| The launcher says Claude Code is still not available | Close the window and double-click Start Coach again |
| `claude` not found after installing by hand | Open a new terminal window. Still missing: [install troubleshooting](https://code.claude.com/docs/en/troubleshoot-install) |
| The coach says it can't read the sheet | Type `/mcp` in the coach window and check Google Drive is listed and signed in |
| The coach can't type into the sheet | Type `/chrome`. Make sure Chrome is open and signed in to the Google account that owns the sheet |
| `python` not found on Windows | Try `py --version`. If that works, use `py` in place of `python` |
| Overleaf won't accept the coach's edits | Ask the coach for the file and paste it into Overleaf yourself |
| Mac says the launcher can't be run | In Terminal: `cd` to the folder, then `bash "Start Coach - Mac.command"` |
