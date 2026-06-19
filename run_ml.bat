@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo   Beef Price Model - ML 파이프라인 실행
echo ============================================================
python src\run_ml.py %*
echo.
echo (창을 닫으려면 아무 키나 누르세요)
pause >nul
