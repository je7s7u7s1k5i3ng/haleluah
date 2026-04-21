---
description: DB 에 쌓인 스냅샷으로 황금키워드 리포트 생성
---

API 호출 없이 DB 만으로 리포트를 만든다.

1. `scout summary --json` — DB 전체 규모 / 수집 기간
2. `scout query --grade S --limit 20 --json` — S 급 상위 20
3. `scout query --grade A --limit 30 --json` — A 급 상위 30
4. `scout query --max-comp 0.3 --min-vol 1000 --order golden_score --limit 20 --json` — 최고 황금
5. `scout query --min-comp 2.0 --limit 10 --json` — 포화 키워드 (피해야 할 군)

각 JSON 을 읽고 아래 마크다운 리포트를 생성:

```
## 수집 현황
- 총 키워드: N, S: _, A: _, B: _
- 수집 기간: YYYY-MM-DD ~ YYYY-MM-DD

## S급 TOP 20 (최우선)
| 키워드 | 총검색 | 상품수 | 경쟁강도 | 황금점수 |
...

## A급 TOP 30
...

## ⚠️ 포화 키워드 (피할 것)
- 경쟁강도 2.0 이상
...

## 권장 다음 액션
1. ...
2. ...
```

사용자가 요청하지 않은 이상 엑셀 파일은 만들지 말고 **마크다운 리포트만 채팅에 출력**.
