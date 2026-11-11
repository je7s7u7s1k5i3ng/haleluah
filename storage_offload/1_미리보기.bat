@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [미리보기] 아무것도 옮기지 않고 옮길 목록과 용량만 보여줍니다.
python offload_to_gdrive.py
pause
