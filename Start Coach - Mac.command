#!/bin/bash
# Double-click to start your career coach (macOS; also works on Linux from a
# terminal).
#
# Each time it: checks Claude Code and Python are installed (and offers to
# install what is missing), then opens your tracker sheet and the coach.
# The first time, it also opens the two pages where you connect Google Drive
# and Chrome. Nothing is installed without asking first.
#
#   DRY_RUN=1   print what would be opened or started, and start nothing

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

step "Starting the coach..."
if [ -n "$DRY_RUN" ]; then say "[dry run] would run: claude --chrome \"$prompt\""; exit 0; fi
exec claude --chrome "$prompt"
