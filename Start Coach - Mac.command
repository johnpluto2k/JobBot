#!/bin/bash
# Double-click to start your career coach (macOS; also works on Linux from a
# terminal).
#
# Each time it: checks Claude Code and Python are installed (and offers to
# install what is missing), then opens your tracker sheet and the coach.
# The first time, it also opens the two pages where you connect Google Drive
# and Chrome. Nothing is installed without asking first.
#
# Where the coach opens: if the Orca app is installed and this folder is open
# in it, the coach opens as a "Career Coach" tab in Orca. Otherwise it opens
# right here in this window.
#
#   DRY_RUN=1   print what would be opened or started, and start nothing
#   NO_ORCA=1   open the coach in this window even if Orca is installed

cd "$(dirname "$0")" || exit 1

say()  { printf '  %s\n' "$1"; }
step() { printf '\n  \033[36m%s\033[0m\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }
open_page() {
  if [ -n "$DRY_RUN" ]; then say "[dry run] would open $1"
  elif have open; then open "$1"
  else xdg-open "$1" >/dev/null 2>&1
  fi
}
ask() {  # ask "question" -> reply in $REPLY; empty in a dry run
  if [ -n "$DRY_RUN" ]; then REPLY="$2"; else read -r -p "  $1 " REPLY; fi
}

printf '\n  \033[32mCareer Coach\033[0m\n'

# ---- 1. Claude Code ---------------------------------------------------------
if ! have claude; then
  step "Claude Code is not installed yet."
  say "It is the program the coach runs in. You need a paid Claude plan to sign in."
  ask "Install it now? (Y/n)" "n"
  case "$REPLY" in
    [nN]*) ;;
    *) curl -fsSL https://claude.ai/install.sh | bash
       export PATH="$HOME/.local/bin:$PATH" ;;
  esac
  if ! have claude; then
    step "Claude Code is still not available in this window."
    say "Close this window and double-click Start Coach again."
    say "To install it by hand, see SETUP.md, step 1."
    exit 1
  fi
fi

# ---- 2. Python and the PDF checker's one package ----------------------------
python=""
for candidate in python3 python; do
  if have "$candidate" && "$candidate" --version >/dev/null 2>&1; then python="$candidate"; break; fi
done
if [ -z "$python" ]; then
  step "Python is not installed."
  say "The coach uses it to measure your resume PDF. Everything else works without it."
  say "Download it from https://www.python.org/downloads/ and start the coach again."
elif ! "$python" -c "import pdfminer" >/dev/null 2>&1; then
  step "Installing the resume checker's one Python package..."
  if [ -n "$DRY_RUN" ]; then say "[dry run] would run: $python -m pip install -r tools/requirements.txt"
  else "$python" -m pip install --quiet -r tools/requirements.txt \
       || "$python" -m pip install --quiet --user -r tools/requirements.txt
  fi
fi

# ---- 3. First run, or a normal day ------------------------------------------
if [ ! -f coach/COACH.md ]; then
  step "First time here. Two things to connect, once:"
  say "1. Google Drive, so the coach can read your tracker sheet."
  say "      On the page that opens, add Google Drive and sign in."
  say "2. The Claude extension for Chrome, so the coach can add rows to your sheet."
  say "      On the page that opens, click Add to Chrome and sign in."
  ask "Press Enter to open both pages (or type s to skip)" ""
  case "$REPLY" in
    [sS]*) ;;
    *) open_page "https://claude.ai/customize/connectors"
       open_page "https://chromewebstore.google.com/detail/claude/fcoeoabgfenejglbffodgkkbkcdhcgfn"
       ask "When both are connected, press Enter to meet your coach" "" ;;
  esac
  prompt="set me up"
else
  if [ -f coach/tracker.md ]; then
    sheet=$(grep -Eo 'https://docs\.google\.com/spreadsheets/[^[:space:])>]+' coach/tracker.md | head -n 1)
    [ -n "$sheet" ] && open_page "$sheet"
  fi
  prompt="Where are we?"
fi

# ---- 4. Open the coach: in Orca when this folder is open there, else here -----
step "Starting the coach..."
command="claude --chrome \"$prompt\""

# Find Orca's command-line tool. On Linux a bare `orca` is the GNOME screen
# reader, not this app, so only `orca-ide` is used there.
orca_cli=""
if [ -n "$ORCA_CLI_COMMAND" ]; then orca_cli="$ORCA_CLI_COMMAND"
elif [ "$(uname)" = "Linux" ]; then have orca-ide && orca_cli="orca-ide"
elif have orca; then orca_cli="orca"
fi

if [ -n "$orca_cli" ] && [ -z "$NO_ORCA" ]; then
  selector="path:$(pwd)"
  if [ -n "$DRY_RUN" ]; then
    say "[dry run] Orca is installed; would open a Career Coach tab there if this folder is open in it: $command"
    exit 0
  fi
  "$orca_cli" open --json >/dev/null 2>&1      # starts Orca, or brings its window forward
  tries=0
  until "$orca_cli" status --json 2>/dev/null | grep -q '"reachable": *true' || [ "$tries" -ge 30 ]; do
    tries=$((tries + 1)); sleep 1
  done
  if "$orca_cli" worktree show --worktree "$selector" --json 2>/dev/null | grep -q '"ok": *true'; then
    if "$orca_cli" terminal create --worktree "$selector" --title "Career Coach" \
         --command "$command" --focus --json 2>/dev/null | grep -q '"ok": *true'; then
      say "Your coach is open in Orca."
      exit 0
    fi
    say "Could not open a tab in Orca, so the coach will open here."
  else
    say "Orca is installed, but this folder is not open in it, so the coach will open here."
    say "(Add this folder as a project in Orca to have the coach open there next time.)"
  fi
fi

if [ -n "$DRY_RUN" ]; then say "[dry run] would run here: $command"; exit 0; fi
exec claude --chrome "$prompt"
