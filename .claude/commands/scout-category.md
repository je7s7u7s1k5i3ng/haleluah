---
description: 카테고리 단위로 황금키워드 자동 발굴
argument-hint: <카테고리명>
---

사용자가 `$ARGUMENTS` 카테고리에서 황금키워드를 찾길 원한다.

아래 순서로 진행하되 **모든 CLI 호출은 `--json` 플래그** 를 쓰고 `orjson` 출력만 신뢰하라:

1. `scout summary --json` 으로 쿼터 확인. 쇼핑 잔여 < 3000 이면 사용자에게 경고.
2. 카테고리에 맞는 시드 5~15개를 네가 도메인 지식으로 생성.
3. `scout seeds-write data/seeds_run.txt <시드들>` 로 저장.
4. `scout estimate <시드수> --depth 2 --max 3000 --json` 로 사전 예측.
   warnings 가 비어있지 않으면 사용자 확인 후 진행.
5. `scout mine data/seeds_run.txt --depth 2 --max 3000 --min-vol 300 --max-comp 1.2 --out out/$ARGUMENTS.xlsx --json --top 30`
6. 결과 JSON 의 `top` 배열을 S→A→B 순으로 분석하고:
   - 상위 10개 황금키워드 표
   - 등급 분포
   - 재공략 추천 키워드 3개 (comp_idx 높은 것에 수식어 붙이는 안)
   를 간결하게 보고.
7. Excel 경로 (`out/$ARGUMENTS.xlsx`) 를 알려주고 사용자에게 다음 액션 제안.
