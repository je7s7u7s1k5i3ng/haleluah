# Item Scout — Claude Code 에이전트 가이드

이 저장소는 **네이버 API 기반 키워드 스카우트** 도구입니다. 사람이 `scout` CLI 로도 쓰지만,
**Claude Code 가 오케스트레이터**로 붙어서 "전략 결정 → 수집 명령 → 결과 분석 → 다음 명령"의
루프를 돌리도록 설계되어 있습니다.

## 역할 분담

| 레이어 | 담당 |
|---|---|
| **Claude Code (당신)** | 어떤 카테고리·시드를 수집할지 결정, JSON 결과 해석, 다음 루프 시드 생성, 비즈니스 판단 |
| **Python `scout` CLI** | 네이버 API 호출, 레이트 제한, 상품수/검색량 수집, SQLite 저장, 엑셀 내보내기 |
| **SQLite DB** | 세션 간 공유 상태. 과거 수집 결과 / 쿼터 / 랭크 |

사람이 자연어로 "캠핑 용품 황금키워드 찾아줘" 라고 하면, 당신이 시드를 정해 `scout` 를 호출하고,
`--json` 출력만 읽어서 해석·보고합니다. **절대 CLI 출력의 숫자를 추측하거나 합성하지 마세요.
모든 수치는 `--json` 결과에서만 인용하세요.**

## 표준 워크플로우

### 1. 상태 점검
```bash
scout summary --json
```
DB 크기, 오늘 API 호출량, 쇼핑 25k 잔여. 쿼터 남았는지 먼저 확인.

### 2. 사전 예측
```bash
scout estimate <seed_count> --depth 2 --max 2000 --json
```
warnings 가 있으면 사용자에게 확인 후 진행.

### 3. 수집
- **진단 (1개)**: `scout search "<키워드>" --json`
- **연관 확장 (빠름, 저렴)**: `scout expand "<시드>" --depth 2 --max 500 --json`
- **채굴 (수백~수천)**: 시드 파일 작성 후 `scout mine seeds.txt --json --top 30`
- **대량 (수만)**: `scout bulk-mine seeds.txt --chunk 500 --depth 2 --json --top 50`

시드 파일은 `scout seeds-write <path> <seed1> <seed2> ...` 로 Claude 가 생성 가능.

### 4. DB 조회 (API 호출 없이 재분석)
```bash
scout query --grade S --max-comp 0.5 --limit 30 --json
scout query --contains "무선" --order competition --limit 20 --json
scout top --min-vol 1000 --max-comp 0.5 --json
```

### 5. 다음 루프 시드 제안
```bash
scout suggest --category 디지털가전 --json
```
`narrow_candidates` = 경쟁 높은 키워드 → 수식어 붙여 롱테일로 재시도하라는 힌트.

## 판단 규칙 (Claude 가 쓸 것)

- **S 등급**: 경쟁강도 < 0.3 AND 총검색수 ≥ 1000 → 최우선 추천
- **A 등급**: 경쟁강도 < 0.8 AND 총검색수 ≥ 500
- **B 등급**: 경쟁강도 < 1.5
- **C/D** 는 롱테일로 쪼갤 여지가 있다는 신호. `narrow_candidates` 로 활용

### 롱테일 생성 전략

경쟁강도가 높은 키워드 `K` 를 만나면, 아래 조합으로 시드를 확장:
```
K + 색상(검정/화이트/베이지 ...)
K + 사용자(여성/남성/아이/노인)
K + 용도(캠핑/사무실/여행)
K + 소재/브랜드 제외
K + 가격대(저렴/고급)
```
→ `scout expand` 로 먼저 확장해 검색량이 남는지 확인 후 `mine`.

## 컨텍스트 효율 규칙

- `--json` + `--top N` 로 항상 **상위 N개만** 받기. 전체 덤프 금지.
- 수만 개 결과가 필요하면 DB 에 쌓고 `scout query` 로 페이지네이션.
- Excel 결과는 경로만 보고, 필요 시 `pandas` 로 샘플링 (첫 20행) 하여 확인.

## 자주 하는 실수 체크리스트

1. ❌ `scout mine` 을 매번 실행 → ✅ `scout query` 로 먼저 DB 확인 (24h 캐시)
2. ❌ depth=3 + 시드 100개 → ✅ `estimate` 로 warnings 확인
3. ❌ JSON 없이 표 파싱 → ✅ 항상 `--json`
4. ❌ API 키를 물어봄 → ✅ `.env` 확인 요청만 (키 누출 금지)

## 명령어 요약 (cheatsheet)

```bash
scout summary --json                         # 현황
scout estimate 100 --depth 2 --json          # 사전 예측
scout expand "캠핑" --max 500 --json          # 연관 키워드
scout seeds-write seeds.txt 캠핑 차박 오토캠핑
scout mine seeds.txt --json --top 30         # 채굴
scout bulk-mine seeds.txt --chunk 500 --json # 대량
scout query --grade S --grade A --json       # DB 조회
scout suggest --json                         # 다음 시드
scout top --min-vol 1000 --max-comp 0.5 --json
scout trend "무선이어폰" --category 디지털가전 --period week
```

## API 키 위치

`.env` 에 아래 값 필요. 없으면 사용자에게 발급처 안내하고 직접 채우도록 유도.

| 키 | 발급처 |
|---|---|
| `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` | https://developers.naver.com/apps |
| `SEARCHAD_API_KEY` / `SEARCHAD_SECRET_KEY` / `SEARCHAD_CUSTOMER_ID` | https://searchad.naver.com |

## 테스트 / 빌드

- `pytest -q` — 유닛 테스트
- `scripts/build_windows.ps1` — Windows `scout.exe` 단일 파일 빌드
