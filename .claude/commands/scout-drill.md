---
description: 경쟁 높은 키워드를 롱테일로 쪼개 재공략
argument-hint: <타겟 키워드>
---

타겟 키워드: `$ARGUMENTS`

이 키워드가 경쟁강도가 높을 때 쓰는 루프. 목표는 같은 수요를 노리되 **롱테일**로 진입점 확보.

1. `scout search "$ARGUMENTS" --json` — 현재 상태 파악
2. `scout expand "$ARGUMENTS" --depth 2 --max 300 --json` — 연관 키워드 빠르게 스캔
3. JSON 결과에서 `total_qc >= 300` 이면서 아직 긴 꼬리로 보이는 키워드 상위 15개 선정
4. `scout seeds-write data/narrow_$ARGUMENTS.txt <선정된 시드들>`
5. `scout mine data/narrow_$ARGUMENTS.txt --depth 1 --max 500 --min-vol 200 --max-comp 0.8 --out out/narrow_$ARGUMENTS.xlsx --json --top 20`
6. S/A 등급만 골라 표로 보고, 각 키워드에 대한 **상품 기획 힌트** 1줄 첨부:
   - 예: "캠핑 테이블 알루미늄 → 경량·휴대성 포인트로 마케팅 유리"

API 호출 최소화를 위해 2단계 `expand` 결과가 이미 `total_qc < 100` 뿐이면 4~5단계 생략하고 다른 접근 제안.
