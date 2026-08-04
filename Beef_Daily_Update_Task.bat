@echo off
rem Task Scheduler runner - no pause, logs to logs\pipeline_task.log
rem For manual runs use Beef_Daily_Update.bat
rem (ASCII only in this file: Korean text before chcp breaks cp949 batch parsing)
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUNBUFFERED=1"

if not exist "logs" mkdir "logs"

set "PYEXE="
if exist ".venv\Scripts\python.exe" set "PYEXE=%~dp0.venv\Scripts\python.exe"
if not defined PYEXE if exist "venv\Scripts\python.exe" set "PYEXE=%~dp0venv\Scripts\python.exe"
if not defined PYEXE set "PYEXE=python"

echo. >> "logs\pipeline_task.log"
echo ===== %date% %time% run_auto START ===== >> "logs\pipeline_task.log"
"%PYEXE%" "%~dp0src\run_auto.py" %* >> "logs\pipeline_task.log" 2>&1
set "RC=%ERRORLEVEL%"
echo ===== %date% %time% run_auto END (exit %RC%) ===== >> "logs\pipeline_task.log"
exit /b %RC%
