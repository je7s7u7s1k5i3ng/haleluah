# Item Scout

네이버 공식 API 3종(**쇼핑 검색 / 검색광고 / 데이터랩 쇼핑인사이트**)을 써서
키워드의 **상품수·월검색량·경쟁강도**를 대량으로 수집·분석하고 **황금 키워드**를
발굴하는 파이썬 CLI 도구입니다. Windows `.exe` 단일 바이너리 배포 지원.

## ✨ 성능/대량 수집 기능

- **HTTP/2** 재사용 커넥션 풀 + **orjson** 파싱
- **적응형 레이트리미터**: 429/Retry-After 자동 감지 → RPS 절반 감속 → 점진 복원
- **체크포인트(JSONL)**: 중단 후 재개. 이미 처리한 키워드 스킵
- **스트리밍 수집**: 키워드 하나 끝날 때마다 DB/엑셀에 흘려 쓰기 (수만 개도 메모리 안정)
- **배치 분할 (`bulk-mine`)**: 시드 수천~수만 개를 `--chunk` 단위로 쪼개 병렬 처리
- **Rich 진행바 + 실시간 통계**: 완료 수 / 에러 수 / ETA
- **SQLite WAL 모드** 스냅샷 (일자별 추이 저장)

## 📊 지표

| 지표 | 정의 |
|---|---|
| 총검색수 | `monthlyPcQcCnt + monthlyMobileQcCnt` (검색광고 API) |
| 상품수 | 쇼핑 API `total` |
| 경쟁강도 | `상품수 / 총검색수` (낮을수록 좋음) |
| 황금점수 | `총검색수 / log10(상품수 + 10)` |

- **S급** 경쟁강도 < 0.3 AND 총검색수 ≥ 1000
- **A급** 경쟁강도 < 0.8 AND 총검색수 ≥ 500
- **B급** 경쟁강도 < 1.5

## 🛠 설치 (Windows 권장)

### 옵션 1: uv 로 바로 실행
```powershell
# uv 설치
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 프로젝트 설치
uv venv
uv pip install -e ".[dev]"

# API 키 입력
copy .env.example .env
notepad .env

# 실행
.\.venv\Scripts\scout search "무선이어폰"
```

### 옵션 2: `scout.exe` 빌드 (단일 파일, 파이썬 미설치 PC에 배포)
```powershell
.\scripts\build_windows.ps1
# 결과: dist\scout.exe
.\dist\scout.exe search "무선이어폰"
```

## 🚀 사용법

### 단일 키워드 진단
```bash
scout search "무선이어폰"
```

### 연관 키워드 확장 (쇼핑 total 미조회, 빠름)
```bash
scout expand "캠핑" --depth 2 --max 1000
```

### 중급 채굴 (수백~수천 키워드)
```bash
scout mine seeds.txt --depth 2 --max 2000 \
    --min-vol 500 --max-comp 1.0 --out gold.xlsx
# 중단되어도 재실행 시 --resume (기본 on) 으로 이어감
```

### 🔥 대량 채굴 (수만 키워드)
```bash
scout bulk-mine big_seeds.txt \
    --chunk 500 --depth 2 --max 50000 \
    --min-vol 300 --max-comp 1.5 \
    --out-dir ./out
# 시드를 500개씩 쪼개 배치별로 처리.
# 각 배치 완료 시 gold_batch_0001.xlsx ... 저장.
# 모든 배치 종료 후 gold_all.xlsx + all_metrics.xlsx 통합.
# 네트워크 끊겨도 재실행하면 미완 배치만 이어서 진행.
```

### DB 에 쌓인 스냅샷에서 TOP 뽑기
```bash
scout top --min-vol 1000 --max-comp 0.5 --limit 100
```

### 순위 추적
```bash
scout track 123456789 --keyword "수면양말"
```

### 카테고리 트렌드
```bash
scout trend "무선이어폰" --category 디지털가전 --days 180 --period week
scout categories   # 지원 카테고리 목록
```

## 🗂 시드 파일 형식

한 줄에 하나씩. 빈 줄 무시.

```
캠핑
무선이어폰
아기띠
...
```

## 🔑 API 키 발급

| API | 발급처 | 필요한 값 |
|---|---|---|
| 쇼핑 검색 / 데이터랩 | [네이버 개발자센터](https://developers.naver.com/apps) | Client ID / Secret |
| 검색광고 | [네이버 검색광고](https://searchad.naver.com) > 도구 > API 사용 관리 | API Key / Secret / Customer ID |

## ⚙️ 환경변수 (`.env`)

```dotenv
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=
SEARCHAD_API_KEY=
SEARCHAD_SECRET_KEY=
SEARCHAD_CUSTOMER_ID=

SCOUT_CONCURRENCY=20          # 동시 요청 수
SCOUT_RPS_SHOPPING=8          # 쇼핑 API 초당 요청 상한
SCOUT_RPS_SEARCHAD=4          # 광고 API 초당 요청 상한
SCOUT_CACHE_TTL_HOURS=24
SCOUT_DB_PATH=./data/scout.db
SCOUT_CHECKPOINT_DIR=./data/checkpoints
SCOUT_HTTP2=1
```

## 🧪 테스트

```bash
pytest -q   # 19개 테스트
```

## 📐 아키텍처

```
src/item_scout/
├── clients/
│   ├── http.py         공용 AsyncClient + AdaptiveLimiter + 429 백오프
│   ├── shopping.py     쇼핑 검색 (total, items, find_rank)
│   ├── searchad.py     검색광고 (HMAC-SHA256 서명, keywordstool)
│   └── datalab.py      데이터랩 (category_keywords_trend, category_trend)
├── scout/
│   ├── analyzer.py     KeywordMetric, filter_golden, 등급
│   ├── collector.py    BFS 확장, 스트리밍 수집, 체크포인트
│   ├── checkpoint.py   JSONL 기반 재개 지원
│   └── category_codes.py
├── storage/db.py       SQLite WAL + 스냅샷 + 랭크 트래킹
├── cli.py              typer + rich
└── __main__.py         PyInstaller 진입점
```
