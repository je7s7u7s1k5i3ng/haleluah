@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [실행] F 원본을 G드라이브로 옮깁니다. 한 번에 50GB까지. 중단하려면 Ctrl+C
pause
python offload_to_gdrive.py --execute
pause
