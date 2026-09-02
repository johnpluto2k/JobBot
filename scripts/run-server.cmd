@echo off
title Job Bot Server
cd /d "C:\ClaudeProjects\Job Bot"

echo.
echo   === Job Bot backend ===
echo   Dashboard: http://localhost:8000
echo   Press Ctrl+C to stop.
echo.

REM ---- Update to the newest code (fast-forward only; see the script) -------
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\sync-to-latest.ps1"

REM ---- Rebuild the web UI only when the code has changed ---------------------
:check_build
for /f "delims=" %%i in ('git rev-parse HEAD') do set "SHA=%%i"
set "BUILT="
if exist "data\.built-sha" set /p BUILT=<data\.built-sha
if "%BUILT%"=="%SHA%" goto :run
if not exist "web\node_modules" goto :npm_install
goto :build

:npm_install
echo   Installing web dependencies (first time, may take a minute)...
cd web
call npm install
cd ..

:build
echo   Building the dashboard UI...
cd web
call npm run build
if errorlevel 1 goto :build_failed
cd ..
(echo %SHA%)>data\.built-sha
goto :run

:build_failed
cd /d "C:\ClaudeProjects\Job Bot"
echo.
echo   [!] The UI build failed - starting with the previously built version.
echo.

:run
python -m uvicorn job_bot.api:app --port 8000
echo.
echo   Job Bot backend stopped.
pause
