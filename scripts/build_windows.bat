@echo off
REM Windows 빌드 스크립트 (CMD)
setlocal enabledelayedexpansion

where uv >nul 2>nul
if errorlevel 1 (
    echo uv 설치 중...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
)

echo === 가상환경 + 의존성 ===
uv venv || goto :err
uv pip install -e ".[dev,build]" || goto :err

echo === 테스트 ===
.\.venv\Scripts\pytest -q || goto :err

echo === PyInstaller 빌드 ===
.\.venv\Scripts\pyinstaller scout.spec --clean --noconfirm || goto :err

echo.
echo 빌드 완료: dist\scout.exe
echo 사용: dist\scout.exe search "무선이어폰"
exit /b 0

:err
echo 빌드 실패
exit /b 1
