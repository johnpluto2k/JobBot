@echo off
title Job Bot - Daily Pipeline
cd /d "C:\ClaudeProjects\Job Bot"
echo ============================================================
echo   Job Bot - Daily Pipeline
echo   Finds jobs, tailors resumes, drafts follow-ups, triages
echo   your recruiter inbox, and writes a daily summary.
echo   It DRAFTS and FINDS only - it never sends or submits.
echo ============================================================
echo.
echo Launching Claude Code in the Job Bot folder...
echo (If it does not start on its own, paste this line:)
echo     Run the daily pipeline in daily_pipeline_prompt.md
echo.
claude "Run the daily pipeline in daily_pipeline_prompt.md."
