@echo off
REM Double-click to start your career coach. It checks that everything is
REM installed, opens your tracker sheet, and opens the coach.
REM All the logic is in tools\start.ps1.
title Career Coach
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "tools\start.ps1" %*
