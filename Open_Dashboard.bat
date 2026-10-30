@echo off
rem Regenerate and open the local HTML dashboard (no Streamlit server needed)
rem (ASCII only in this file)
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"

set "PYEXE="
if exist ".venv\Scripts\python.exe" set "PYEXE=%~dp0.venv\Scripts\python.exe"
if not defined PYEXE if exist "venv\Scripts\python.exe" set "PYEXE=%~dp0venv\Scripts\python.exe"
if not defined PYEXE set "PYEXE=python"

"%PYEXE%" "%~dp0src\utils\build_html_dashboard.py"
if errorlevel 1 echo [!] Some sections could not be built - see messages above.
if exist "dashboard\beef_dashboard.html" start "" "dashboard\beef_dashboard.html"
