@echo off
rem Double-click launcher for this project (Windows).
rem
rem A .ps1 file is not executable by double-click: Explorer opens it in Notepad, and
rem PowerShell refuses to run unsigned scripts under the default policy. This wrapper
rem calls the real script with the policy bypassed for this one run, keeps the window
rem open when something fails, and forwards any arguments (-NoStart, -SkipSync).
rem
rem Usage: double-click this file, or from a terminal:
rem   start.bat
rem   start.bat -NoStart
rem   start.bat -SkipSync

setlocal
cd /d "%~dp0"

echo ==== kotaemon launcher ====
echo repository: %CD%
echo.

where powershell >nul 2>nul
if errorlevel 1 (
    echo [ERROR] PowerShell was not found on PATH.
    echo         Start the app manually instead:
    echo         .venv\Scripts\python.exe -X utf8 app.py
    echo.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap_windows.ps1" %*
set "RC=%ERRORLEVEL%"

rem Find the newest launcher log first: `set` inside the error block below would be
rem expanded at parse time and print nothing.
set "LOG="
for /f "delims=" %%F in ('dir /b /o-d "ktem_app_data\logs\bootstrap-*.log" 2^>nul') do (
    if not defined LOG set "LOG=ktem_app_data\logs\%%F"
)

if not "%RC%"=="0" (
    echo.
    echo [ERROR] The launcher exited with code %RC%.
    if defined LOG echo         Log: %LOG%
    echo         App log: ktem_app_data\logs\app.log
    echo         Scroll up for the first error line.
    echo.
    pause
)

exit /b %RC%
