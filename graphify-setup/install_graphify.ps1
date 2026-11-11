# ============================================================
#  Graphify 설치 + Claude Code 연동 자동 스크립트 (Windows)
#  대상 폴더: J:\프로그램 관리\직접 촬영 영상 AI로 화면 화려하게 하는 방법 프로그램\영상제작 종류별 샘플
#  실행: 같은 폴더의 "설치하기.bat" 더블클릭 (또는 PowerShell에서 직접 실행)
# ============================================================
param(
    [string]$Target = "J:\프로그램 관리\직접 촬영 영상 AI로 화면 화려하게 하는 방법 프로그램\영상제작 종류별 샘플"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Step($n, $msg) { Write-Host ""; Write-Host "[$n/7] $msg" -ForegroundColor Cyan }
function Ok($msg)       { Write-Host "  OK  $msg" -ForegroundColor Green }
function Warn($msg)     { Write-Host "  !!  $msg" -ForegroundColor Yellow }
function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user    = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user;$env:USERPROFILE\.local\bin"
}

# --- 1. 대상 폴더 확인 ---------------------------------------
Step 1 "대상 폴더 확인"
if (-not (Test-Path -LiteralPath $Target)) {
    New-Item -ItemType Directory -Path $Target -Force | Out-Null
    Warn "폴더가 없어서 새로 만들었습니다: $Target"
} else {
    Ok $Target
}
$log = Join-Path $Target "graphify-install.log"
Start-Transcript -LiteralPath $log -Append | Out-Null

try {
    # --- 2. uv 설치 확인 -------------------------------------
    Step 2 "uv (파이썬 도구 관리자) 확인"
    Refresh-Path
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Warn "uv가 없습니다. 설치합니다."
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            winget install --id astral-sh.uv -e --accept-source-agreements --accept-package-agreements
        } else {
            Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
        }
        Refresh-Path
    }
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw "uv 설치 후에도 찾을 수 없습니다. PowerShell 창을 새로 열고 다시 실행하세요."
    }
    Ok (uv --version)

    # --- 3. graphify 설치 (영상/PDF/오피스/MCP 확장 포함) ----
    Step 3 "graphify 설치 (패키지 이름: graphifyy, y 두 개)"
    uv tool install --force --python 3.12 "graphifyy[video,pdf,office,mcp]"
    if ($LASTEXITCODE -ne 0) { throw "graphify 설치 실패 (uv tool install)" }
    uv tool update-shell | Out-Null
    Refresh-Path
    if (-not (Get-Command graphify -ErrorAction SilentlyContinue)) {
        throw "graphify 명령을 찾을 수 없습니다. PowerShell 창을 새로 열고 다시 실행하세요."
    }
    Ok (graphify --version)

    # --- 4. 사용자 전체 Claude Code 스킬 등록 ----------------
    Step 4 "Claude Code 스킬 등록 (사용자 전체: ~/.claude/skills/graphify)"
    graphify install
    if ($LASTEXITCODE -ne 0) { throw "graphify install 실패" }
    Ok "모든 폴더에서 /graphify 사용 가능"

    # --- 5. 대상 폴더 전용 연동 (스킬 + CLAUDE.md + 훅) ------
    Step 5 "대상 폴더 전용 연동 (.claude/ 와 CLAUDE.md)"
    Push-Location -LiteralPath $Target
    graphify install --project
    if ($LASTEXITCODE -ne 0) { throw "graphify install --project 실패" }
    graphify claude install --project
    if ($LASTEXITCODE -ne 0) { throw "graphify claude install --project 실패" }
    Ok "기존 CLAUDE.md 내용은 그대로 두고 graphify 규칙만 추가됨"

    # --- 6. 제외 목록 (.graphifyignore) ----------------------
    Step 6 "제외 목록 파일 (.graphifyignore)"
    $ignore = Join-Path $Target ".graphifyignore"
    if (-not (Test-Path -LiteralPath $ignore)) {
        @(
            "# graphify가 분석하지 않을 파일/폴더 (.gitignore 문법)",
            "graphify-out/",
            "graphify-install.log",
            "*.tmp",
            "*.part",
            "Thumbs.db",
            "desktop.ini",
            "# 용량 큰 원본 영상을 빼고 싶으면 아래 줄의 # 을 지우세요",
            "# *.mov",
            "# *.mp4"
        ) | Set-Content -LiteralPath $ignore -Encoding UTF8
        Ok "생성: $ignore"
    } else {
        Ok "이미 있음 (변경 안 함): $ignore"
    }
    Pop-Location

    # --- 7. 최종 점검 ----------------------------------------
    Step 7 "최종 점검"
    $checks = @(
        @{ p = "$env:USERPROFILE\.claude\skills\graphify\SKILL.md"; n = "사용자 스킬" },
        @{ p = (Join-Path $Target ".claude\skills\graphify\SKILL.md"); n = "폴더 스킬" },
        @{ p = (Join-Path $Target ".claude\settings.json");          n = "훅 설정" },
        @{ p = (Join-Path $Target "CLAUDE.md");                      n = "CLAUDE.md 규칙" }
    )
    $fail = 0
    foreach ($c in $checks) {
        if (Test-Path -LiteralPath $c.p) { Ok "$($c.n): $($c.p)" } else { Warn "없음 - $($c.n): $($c.p)"; $fail++ }
    }
    if ($fail -gt 0) { throw "점검 실패 항목 $fail 개" }

    Write-Host ""
    Write-Host "설치 완료" -ForegroundColor Green
    Write-Host "다음 단계:"
    Write-Host "  1) Claude 데스크톱 앱 / 터미널을 완전히 껐다가 다시 켭니다 (PATH 반영)"
    Write-Host "  2) Claude Code에서 이 폴더를 엽니다: $Target"
    Write-Host "  3) Claude Code 입력창에 입력:  /graphify ."
    Write-Host "  4) 결과: graphify-out\graph.html (브라우저로 열기), GRAPH_REPORT.md, graph.json"
}
catch {
    Write-Host ""
    Write-Host "설치 중 오류: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "로그 파일: $log"
    exit 1
}
finally {
    Stop-Transcript | Out-Null
}
