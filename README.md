# 뉴스 & 논문 실시간 수집기

뉴스 기사와 학술 논문을 실시간으로 수집하는 파이썬 프로그램입니다.

## 지원 소스

| 종류 | 소스 | API 키 |
|------|------|--------|
| 뉴스 | Google News RSS | 불필요 |
| 뉴스 | 한국 뉴스 (Google News KR) | 불필요 |
| 뉴스 | NewsAPI | 무료 키 필요 |
| 논문 | arXiv | 불필요 |
| 논문 | CrossRef | 불필요 |

## 설치

```bash
pip install -r requirements.txt
```

## 사용법

### 기본 실행 (30분 주기 자동 수집)

```bash
python news_collector.py
```

### 코드에서 사용

```python
from news_collector import RealTimeCollector

collector = RealTimeCollector(output_dir="collected_data")

# 1회 수집
results = collector.collect_all(
    news_queries=["인공지능", "AI"],
    paper_queries=["machine learning"],
    news_categories=["주요뉴스", "기술"],
)

# 주기적 수집 (10분 간격)
collector.start_scheduled(
    news_queries=["인공지능"],
    paper_queries=["deep learning"],
    interval_minutes=10,
)
```

### NewsAPI 키 사용 (선택)

더 많은 뉴스를 수집하려면 [NewsAPI](https://newsapi.org)에서 무료 키를 발급받아 사용할 수 있습니다.

```python
collector = RealTimeCollector(newsapi_key="YOUR_API_KEY")
```

## 출력

수집된 데이터는 `collected_data/` 폴더에 JSON 파일로 저장됩니다.

- `news_20260307_120000.json` - 뉴스 기사
- `papers_20260307_120000.json` - 논문 자료
