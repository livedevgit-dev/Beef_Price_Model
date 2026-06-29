@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo   Beef Price Model - 스마트 자동 실행 (일/주/월 자동 판단)
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
if %RC% neq 0 echo [오류] 종료 코드: %RC%
echo (창을 닫으려면 아무 키나 누르세요)
pause >nul
exit /b %RC%
