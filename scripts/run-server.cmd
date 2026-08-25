@echo off
title Job Bot Server
cd /d "C:\ClaudeProjects\Job Bot"

echo.
echo   === Job Bot backend ===
echo   Dashboard: http://localhost:8000
echo   Press Ctrl+C to stop.
echo.

REM ---- Update to the latest committed code on the 'main' branch --------------
git diff --quiet 2>nul
if errorlevel 1 goto :skip_update
git diff --cached --quiet 2>nul
if errorlevel 1 goto :skip_update
echo   Updating to the latest code on 'main'...
git checkout --detach main >nul 2>&1
goto :check_build

:skip_update
echo   [!] Uncommitted changes in this folder - running them as-is, not updating.

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
