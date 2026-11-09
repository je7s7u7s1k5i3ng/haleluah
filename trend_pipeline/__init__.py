"""
터지는 주제 → 유튜브 교차 분석 파이프라인

"오늘 경제 터진 주제로 수집해줘" 한 번으로:
1) 뉴스에서 오늘 터지는 주제를 숫자로 측정 (hot_topics)
2) 주제별 유튜브 영상의 메타데이터·썸네일·대본 수집 (youtube, transcripts)
3) 뉴스·제목·썸네일·대본 교차 검증 + 터진 영상과 아닌 영상 비교 (analyze)
4) 보고서 작성 (report)

모든 경로는 프로그램 폴더(BASE_DIR) 기준이다. 폴더째 옮기면 그대로 동작한다.
"""

from pathlib import Path

VERSION = "1.0.0"
BASE_DIR = Path(__file__).resolve().parent.parent
