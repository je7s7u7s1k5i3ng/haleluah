# Graphify 설치 + Claude Code 연동 가이드 (Windows)

**대상 폴더**
```
J:\프로그램 관리\직접 촬영 영상 AI로 화면 화려하게 하는 방법 프로그램\영상제작 종류별 샘플
```

**기준 버전**: graphify 0.9.106 (PyPI 패키지 이름 `graphifyy`, y가 두 개) · 공식 저장소 [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify)

---

## 0. 한눈에 보기 (3단계)

| 단계 | 할 일 | 걸리는 시간 |
|---|---|---|
| 1 | 이 폴더의 파일 3개를 대상 폴더에 복사 | 1분 |
| 2 | `install.bat` 더블클릭 → "설치 완료" 확인 | 3~10분 |
| 3 | Claude 앱을 껐다 켜고, Claude Code에서 대상 폴더를 연 뒤 `/graphify .` 입력 | 폴더 크기에 따라 다름 |

---

## 1. Graphify가 뭔가요?

폴더 안의 **코드·문서·PDF·이미지·영상**을 읽어서 **지식 그래프**(무엇이 무엇과 연결되는지 보여주는 지도)로 만들어 주는 도구입니다. Claude Code에 스킬로 붙어서, Claude가 파일을 하나하나 다시 읽는 대신 그래프에 먼저 물어보게 됩니다.

**"영상제작 종류별 샘플" 폴더에서 좋은 점**
- 영상은 내 PC에서 직접 음성을 글로 옮겨(faster-whisper) 그래프에 넣습니다. **외부로 나가지 않습니다.**
- 기획 문서, 이미지, PDF는 Claude가 의미를 읽어 "어떤 샘플이 어떤 효과·장르·기법과 연결되는지" 묶어 줍니다.
- 샘플이 쌓여도 "시네마틱 컬러그레이딩 샘플 어디 있었지?" 같은 질문에 바로 답을 받을 수 있습니다.

**만들어지는 결과물** (`graphify-out\` 폴더)
| 파일 | 용도 |
|---|---|
| `graph.html` | 브라우저로 여는 인터랙티브 지도 (클릭, 검색, 필터) |
| `GRAPH_REPORT.md` | 핵심 개념, 의외의 연결, 추천 질문 요약 |
| `graph.json` | 전체 그래프 데이터. 파일을 다시 읽지 않고 질문할 때 사용 |

---

## 2. 사전 준비

| 항목 | 확인 방법 | 없으면 |
|---|---|---|
| Windows 10/11 | — | — |
| Claude Code (Claude 데스크톱 앱의 Code 탭 또는 터미널 `claude`) | 앱에서 Code 탭이 보이는지 | Claude 데스크톱 앱 최신 버전 설치 |
| 인터넷 연결 | — | 설치할 때만 필요 |
| Python | **필요 없음** | 설치 스크립트가 uv를 통해 Python 3.12를 자동으로 받습니다 |

---

## 3. 자동 설치 (권장)

### 3-1. 파일 복사
이 `graphify-setup` 폴더의 파일 3개를 대상 폴더(`...\영상제작 종류별 샘플`)에 복사합니다.

| 파일 | 역할 |
|---|---|
| `install.bat` | 더블클릭하는 실행 파일 |
| `install_graphify.ps1` | 실제 설치 스크립트 (PowerShell) |
| `GRAPHIFY_설치_연동_가이드.md` | 이 문서 |

> 다른 곳에 두고 실행해도 됩니다. 설치 대상 경로가 스크립트 안에 들어 있습니다.

### 3-2. 실행
`install.bat`를 **더블클릭**합니다. 스크립트가 순서대로 진행합니다.

| 단계 | 하는 일 |
|---|---|
| 1/7 | 대상 폴더 확인 (없으면 생성) |
| 2/7 | `uv`(파이썬 도구 관리자)가 없으면 `winget`으로 설치 |
| 3/7 | `graphifyy[video,pdf,office,mcp]` 설치: 영상 전사, PDF, 워드/엑셀, MCP 서버 포함 |
| 4/7 | `graphify install`: 모든 폴더에서 `/graphify`를 쓸 수 있게 사용자 스킬 등록 (`%USERPROFILE%\.claude\skills\graphify`) |
| 5/7 | `graphify install --project`, `graphify claude install --project`: 대상 폴더 전용 스킬, CLAUDE.md 규칙, 훅 등록 |
| 6/7 | `.graphifyignore`(분석 제외 목록) 생성 |
| 7/7 | 설치된 파일 4개가 모두 있는지 최종 점검 |

마지막에 초록색으로 **"설치 완료"**가 나오면 성공입니다. 진행 기록은 대상 폴더의 `graphify-install.log`에 남습니다.

### 3-3. 설치 후 대상 폴더 구조
```
영상제작 종류별 샘플\
├── .claude\
│   ├── skills\graphify\SKILL.md     ← 이 폴더 전용 graphify 스킬
│   ├── skills\graphify\references\  ← 스킬이 필요할 때 읽는 참고 문서
│   ├── settings.json                ← 훅 (Claude가 검색 전에 그래프부터 확인)
│   └── CLAUDE.md
├── CLAUDE.md                        ← 기존 내용 + "## graphify" 규칙 섹션 추가
├── .graphifyignore                  ← 분석 제외 목록
└── graphify-install.log             ← 설치 기록
```

> **기존 파일 보존 확인됨**: 대상 폴더에 이미 `CLAUDE.md`(헌법 등)나 `.claude\settings.json`이 있으면 **기존 내용은 그대로 두고** graphify 섹션과 훅만 추가합니다. 테스트에서 직접 확인했습니다.

---

## 4. 수동 설치 (자동 설치가 안 될 때)

PowerShell을 열고 한 줄씩 실행합니다.

**① uv 설치**
```powershell
winget install --id astral-sh.uv -e
```
설치 후 **PowerShell 창을 닫고 새로 엽니다.**

**② graphify 설치**
```powershell
uv tool install --python 3.12 "graphifyy[video,pdf,office,mcp]"
```

**③ PATH 등록** (그다음 창을 다시 엽니다)
```powershell
uv tool update-shell
```

**④ 설치 확인**
```powershell
graphify --version
```

**⑤ 사용자 전체 스킬 등록**
```powershell
graphify install
```

**⑥ 대상 폴더로 이동**
```powershell
Set-Location -LiteralPath "J:\프로그램 관리\직접 촬영 영상 AI로 화면 화려하게 하는 방법 프로그램\영상제작 종류별 샘플"
```

**⑦ 폴더 전용 스킬 등록**
```powershell
graphify install --project
```

**⑧ CLAUDE.md 규칙 + 훅 등록**
```powershell
graphify claude install --project
```

---

## 5. Claude Code에서 처음 사용하기

1. **Claude 데스크톱 앱(또는 터미널)을 완전히 종료했다가 다시 켭니다.** 새 PATH가 반영돼야 훅이 `graphify`를 찾습니다.
2. Claude Code에서 대상 폴더를 엽니다.
   - 데스크톱 앱: Code 탭 → 폴더 선택 → `...\영상제작 종류별 샘플`
   - 터미널: 대상 폴더로 이동한 뒤 `claude`
3. Claude Code **입력창**에 입력합니다.
   ```
   /graphify .
   ```
4. 끝나면 `graphify-out\graph.html`을 더블클릭해 브라우저로 엽니다.

> ⚠️ `/graphify .`는 **Claude Code 입력창**에 입력합니다. PowerShell에 입력하면 맨 앞의 `/` 때문에 경로로 인식됩니다. PowerShell에서 직접 쓸 때는 `graphify query ...`처럼 `/` 없이 씁니다.

**연동 확인 방법**
- 입력창에 `/gra`까지만 쳤을 때 `/graphify`가 자동완성 목록에 나오면 스킬이 연결된 것입니다.
- 그래프를 만든 뒤 Claude에게 질문하면, Claude가 파일을 뒤지기 전에 `graphify query`를 먼저 실행합니다. 훅이 동작하는 것입니다.

---

## 6. 일상 사용법

### Claude Code 입력창에서

| 명령 | 용도 |
|---|---|
| `/graphify .` | 처음 그래프 만들기 (전체 분석) |
| `/graphify . --update` | 새로 추가하거나 바꾼 파일만 다시 분석 (샘플 추가 후 권장) |
| `/graphify query "시네마틱 효과에 쓰인 샘플은?"` | 질문으로 관련 부분만 뽑기 |
| `/graphify path "드론 촬영" "컬러그레이딩"` | 두 주제가 어떻게 연결되는지 경로 보기 |
| `/graphify explain "트랜지션"` | 한 개념과 연결된 것 전부 설명 |
| `/graphify add <유튜브 URL>` | 참고 영상을 받아서 글로 옮긴 뒤 그래프에 추가 |
| `/graphify . --wiki` | 그래프를 마크다운 위키로 만들기 |

### 질문 예시 (영상제작 샘플용)
- "장르별로 샘플을 묶어서 보여줘"
- "직접 촬영 영상에 AI 효과를 입힌 샘플 중 가장 많이 연결된 기법은?"
- "쇼츠용 세로 영상 샘플과 롱폼 샘플의 공통 기법은?"
- "아직 샘플이 없는 영상제작 종류는?" (`GRAPH_REPORT.md`의 추천 질문도 참고)

### PowerShell에서 직접 (선택)
```powershell
graphify query "컬러그레이딩 샘플"
```

---

## 7. "항상 그래프 먼저 보기" 연동 (자동 설치에 포함됨)

`graphify claude install --project`가 두 가지를 설정합니다.

**① CLAUDE.md 규칙**: `graph.json`이 있으면 검색이나 파일 읽기 전에 `graphify query`를 먼저 실행하라는 규칙이 추가됩니다.

**② 훅 (`.claude\settings.json`)**
| 훅 | 언제 동작 | 하는 일 |
|---|---|---|
| PreToolUse `Bash\|Grep` | Claude가 검색하기 직전 | 그래프를 먼저 보라고 알림 |
| PreToolUse `Read\|Glob` | Claude가 파일을 하나씩 읽기 직전 | 그래프를 먼저 보라고 알림 |
| SessionStart `compact` | 대화가 압축된 뒤 | 알림 횟수 초기화 |

훅은 알림만 하고 막지는 않습니다(기본 모드, 세션당 최대 5회). 더 강하게 강제하려면 다시 설치합니다.
```powershell
graphify install --project --strict
```

**연동 해제**
```powershell
graphify claude uninstall
```

---

## 8. 선택: MCP 서버로 연동

스킬과 훅만으로 충분합니다. Claude가 그래프를 **도구(tool)**로 직접 호출하게 하고 싶을 때만 추가합니다. **그래프를 한 번 만든 뒤** 대상 폴더에서 실행합니다.

```powershell
claude mcp add graphify -s project -- graphify-mcp graphify-out/graph.json
```

- `-s project`: 이 폴더에서만 쓰도록 `.mcp.json`에 저장합니다.
- 확인: Claude Code에서 `/mcp` 입력 → `graphify`가 connected로 보이면 정상입니다.
- 해제: `claude mcp remove graphify -s project`

> 스킬(CLI)과 MCP를 동시에 쓰면 두 방식이 같은 그래프를 보는지 확인하세요. 하나만 쓰는 것을 권장합니다.

---

## 9. 선택: 자동 갱신

| 방법 | 명령 | 비고 |
|---|---|---|
| 폴더 감시 | `graphify watch .` | 창을 켜 둔 동안 코드 파일이 바뀌면 자동 재구축 (`watch` 확장 필요: 아래 명령) |
| git 커밋 시 | `graphify hook install` | 대상 폴더가 git 저장소일 때만 |
| 수동 (권장) | `/graphify . --update` | 샘플을 추가한 뒤 한 번 실행 |

```powershell
uv tool install --force --python 3.12 "graphifyy[video,pdf,office,mcp,watch]"
```

---

## 10. 개인정보 / 비용

| 자료 | 처리 위치 | 비용 |
|---|---|---|
| 코드 | 내 PC (tree-sitter) | 없음 |
| 영상·음성 | 내 PC (faster-whisper로 전사) | 없음 (CPU 시간만) |
| 문서·PDF·이미지 | 지금 쓰는 Claude Code 세션의 모델 | Claude 사용량에 포함 |
| 텔레메트리 | 없음 | — |

- 질문 기록은 `%USERPROFILE%\.cache\graphify-queries.log`에 남습니다. 끄려면 환경변수 `GRAPHIFY_QUERY_LOG_DISABLE=1`을 설정합니다.

---

## 11. 문제 해결

| 증상 | 해결 |
|---|---|
| `graphify`를 찾을 수 없음 | `uv tool update-shell` 실행 → PowerShell과 Claude 앱을 **모두** 껐다 켜기 |
| `install.bat`가 바로 꺼짐 | PowerShell에서 직접 실행: `powershell -ExecutionPolicy Bypass -File .\install_graphify.ps1` → 오류 메시지 확인 |
| "스크립트를 실행할 수 없습니다" (실행 정책) | `install.bat`로 실행하면 우회됩니다. 직접 실행할 때는 위 명령처럼 `-ExecutionPolicy Bypass` 사용 |
| `winget`이 없음 | 스크립트가 자동으로 공식 uv 설치 스크립트로 대체합니다. 그래도 안 되면 Microsoft Store에서 "앱 설치 관리자" 업데이트 |
| `/graphify`가 자동완성에 안 나옴 | Claude 앱 재시작 → 대상 폴더를 다시 열기. `%USERPROFILE%\.claude\skills\graphify\SKILL.md`가 있는지 확인 |
| 영상이 많아서 너무 오래 걸림 | `.graphifyignore`에서 `# *.mp4`, `# *.mov` 줄의 `#`을 지워 원본 영상 제외 → 기획서·이미지만 분석 |
| 유튜브 추가(`add`) 시 병합 오류 | FFmpeg 설치: `winget install Gyan.FFmpeg` |
| 그래프가 너무 큼 (5,000 노드 이상) | `graph.html`이 커뮤니티 요약 보기로 바뀝니다. 정상 동작입니다 |
| 업데이트 | `uv tool upgrade graphifyy` → `graphify install` → 대상 폴더에서 `graphify install --project` |

---

## 12. 완전 삭제

**① 대상 폴더에서 graphify 연동 제거** (`graphify-out` 폴더까지 지우려면 `--purge`)
```powershell
graphify uninstall
```

**② 프로그램 삭제**
```powershell
uv tool uninstall graphifyy
```

---

## 13. 체크리스트

**설치**
- [ ] 파일 3개를 대상 폴더에 복사
- [ ] `install.bat` 실행 → 7단계 모두 OK, "설치 완료" 확인
- [ ] Claude 앱 재시작

**연동 확인**
- [ ] Claude Code에서 대상 폴더 열기
- [ ] `/gra` 입력 시 `/graphify` 자동완성 확인
- [ ] `/graphify .` 실행 → `graphify-out\graph.html` 생성 확인
- [ ] 질문했을 때 Claude가 `graphify query`를 먼저 실행하는지 확인

**선택**
- [ ] MCP 연동 (`claude mcp add ...`)
- [ ] 샘플 추가 후 `/graphify . --update` 습관화

---

## 출처
- 공식 저장소: https://github.com/Graphify-Labs/graphify
- PyPI: https://pypi.org/project/graphifyy/
- 문서: https://docs.graphify.com
- Claude Code 연동: https://graphify.com/integrations/claude-code
