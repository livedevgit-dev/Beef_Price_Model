@echo off
rem Manual smart run (same path as the scheduler: run_auto.py decides daily/weekly/monthly).
rem Keep this file ASCII-only with CRLF line endings: cmd misreads UTF-8/LF batch files
rem (2026-11-09: Korean text + LF endings made cmd split lines and fail).
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"

echo ============================================================
echo   Beef Price Model - smart run (daily / weekly / monthly auto)
echo ============================================================

set "PYEXE="
if exist ".venv\Scripts\python.exe" set "PYEXE=%~dp0.venv\Scripts\python.exe"
if not defined PYEXE if exist "venv\Scripts\python.exe" set "PYEXE=%~dp0venv\Scripts\python.exe"

if defined PYEXE (
  "%PYEXE%" "%~dp0src\run_auto.py" %*
) else (
  python "%~dp0src\run_auto.py" %*
)

set "RC=%ERRORLEVEL%"
echo.
if %RC% neq 0 echo [ERROR] exit code: %RC%  - see messages above
echo (press any key to close)
pause >nul
exit /b %RC%
