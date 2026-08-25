@echo off
title Job Bot
cd /d "C:\ClaudeProjects\Job Bot"

echo.
echo   Opening Job Bot in Orca...
echo.

REM ---- Make sure Orca is up and its runtime is reachable ---------------------
call orca open >nul 2>&1

REM ---- Ensure the backend + Career Coach tabs exist --------------------------
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\ensure-orca-tabs.ps1"

REM ---- Open the dashboard once the backend answers --------------------------
start "" /min powershell -NoProfile -Command "for ($i=0; $i -lt 180; $i++) { try { if ((Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2).StatusCode -eq 200) { Start-Process 'http://localhost:8000'; break } } catch { Start-Sleep -Milliseconds 500 } }"
exit /b 0
