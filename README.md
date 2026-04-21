# Item Scout

네이버 공식 API 3종(쇼핑 검색 / 검색광고 / 데이터랩 쇼핑인사이트)을 사용하여
키워드의 **상품수·월검색량·경쟁강도**를 대량으로 수집·분석하고, **황금 키워드**를
발굴하는 파이썬 CLI 도구입니다.

## 지표

| 지표 | 정의 |
|---|---|
| 총검색수 | `monthlyPcQcCnt + monthlyMobileQcCnt` (검색광고 API) |
| 상품수 | 쇼핑 API `total` |
| 경쟁강도 | `상품수 / 총검색수` (낮을수록 좋음) |
| 황금점수 | `총검색수 / log10(상품수 + 10)` |

- **S급** 경쟁강도 < 0.3 AND 총검색수 ≥ 1000
- **A급** 경쟁강도 < 0.8 AND 총검색수 ≥ 500
- **B급** 경쟁강도 < 1.5

## 설치

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # API 키 채우기
```

## 사용법

```bash
scout search "무선이어폰"                 # 단일 키워드 진단
scout expand "캠핑" --depth 2             # 연관 키워드 확장
scout mine seeds.txt --min-vol 500 \      # 시드에서 황금키워드 대량 채굴
          --max-comp 1.0 --out gold.xlsx
scout track PRODUCT_ID --keyword "수면양말"  # 노출 순위 추적
scout trend "무선이어폰" --period month     # 데이터랩 트렌드
```

## API 레퍼런스

- 쇼핑 검색: `GET https://openapi.naver.com/v1/search/shop.json`
- 검색광고 연관키워드: `GET https://api.searchad.naver.com/keywordstool`
- 데이터랩 쇼핑인사이트: `POST https://openapi.naver.com/v1/datalab/shopping/category/keywords`
