# Windows 빌드 스크립트 (PowerShell)
# 사용: .\scripts\build_windows.ps1
$ErrorActionPreference = "Stop"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv 설치 중..."
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
}

Write-Host "가상환경 생성 + 의존성 설치 (uv)"
uv venv
uv pip install -e ".[dev,build]"

Write-Host "테스트"
.\.venv\Scripts\pytest -q

Write-Host "PyInstaller 빌드"
.\.venv\Scripts\pyinstaller scout.spec --clean --noconfirm

Write-Host ""
Write-Host "빌드 완료: dist\scout.exe"
Write-Host "사용: dist\scout.exe search '무선이어폰'"
