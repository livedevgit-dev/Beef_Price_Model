@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYEXE="
if exist ".venv\Scripts\python.exe" set "PYEXE=%~dp0.venv\Scripts\python.exe"
if not defined PYEXE if exist "venv\Scripts\python.exe" set "PYEXE=%~dp0venv\Scripts\python.exe"

if defined PYEXE (
  "%PYEXE%" "%~dp0src\run_daily_update.py" %*
) else (
  python "%~dp0src\run_daily_update.py" %*
)

set "RC=%ERRORLEVEL%"
echo.
if %RC% neq 0 echo [오류] 종료 코드: %RC%
pause
exit /b %RC%
