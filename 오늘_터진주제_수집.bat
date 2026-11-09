@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -m trend_pipeline.run %*
echo.
echo Result folder: %~dp0결과
pause
