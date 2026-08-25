@echo off
title Career Coach
cd /d "C:\ClaudeProjects\Job Bot"

echo.
echo   === Career Coach (Claude Code) ===
echo   Grounded in COACH.md + your live pipeline data.
echo   Ask things like "what should I focus on today" or "am I on track".
echo.

claude "Coaching mode. Read COACH.md first, then run python coach_snapshot.py . for a live snapshot. Open with where my job search actually stands right now - lead with anything time-sensitive - one honest observation from the real numbers, and exactly one concrete next move. Then stay in coaching mode for the rest of this conversation."
