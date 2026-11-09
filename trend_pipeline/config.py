"""설정: 카테고리별 씨앗 키워드·RSS, 폴더 경로, API 키(환경변수)"""

import json
import os
from pathlib import Path

from . import BASE_DIR

# 구글 뉴스 한국판 공통 파라미터 (gl·ceid가 없으면 한국판이 아닌 결과가 섞일 수 있음)
GNEWS_KR = "hl=ko&gl=KR&ceid=KR:ko"

CATEGORIES = {
    "경제": {
        "seeds": ["경제", "증시", "코스피", "환율", "금리", "부동산", "물가", "반도체", "수출"],
        "topic_feeds": [
            "https://news.google.com/rss/topics/CAAqIggKIhxDQkFTRHdvSkwyMHZNR2RtY0RFU0FtdHZLQUFQAQ?" + GNEWS_KR,
        ],
        "channel_terms": ["경제", "주식", "투자", "재테크", "부동산", "금리", "환율", "돈"],
    },
    "건강": {
        "seeds": ["건강", "영양제", "다이어트", "혈당", "수면", "갱년기"],
        "topic_feeds": [],
        "channel_terms": ["건강", "의사", "약사", "영양", "음식"],
    },
    "역사": {
        "seeds": ["역사", "유적", "발굴", "고고학", "조선", "고려"],
        "topic_feeds": [],
        "channel_terms": ["역사", "고대", "전쟁", "왕조"],
    },
}


def paths(base_dir=None):
    """프로그램 폴더 아래 표준 경로. 폴더가 없으면 만든다."""
    base = Path(base_dir) if base_dir else BASE_DIR
    p = {
        "base": base,
        "data": base / "data",
        "results": base / "결과",
        "logs": base / "logs",
    }
    for key in ("data", "results", "logs"):
        p[key].mkdir(parents=True, exist_ok=True)
    p["db"] = p["data"] / "trend_history.sqlite"
    p["config"] = base / "config.json"
    return p


def load_settings(base_dir=None):
    """config.json(선택) + 환경변수. API 키는 환경변수 우선, 파일에는 넣지 않는 것을 권장."""
    p = paths(base_dir)
    settings = {
        "top_topics": 5,
        "videos_per_topic": 10,
        "lookback_days": 7,
        "request_sleep_sec": 1.0,
        "transcripts": True,
    }
    if p["config"].exists():
        with open(p["config"], encoding="utf-8") as f:
            settings.update(json.load(f))
    settings["youtube_api_key"] = os.environ.get("YOUTUBE_API_KEY") or settings.get("youtube_api_key")
    settings["naver_client_id"] = os.environ.get("NAVER_CLIENT_ID") or settings.get("naver_client_id")
    settings["naver_client_secret"] = os.environ.get("NAVER_CLIENT_SECRET") or settings.get("naver_client_secret")
    return settings
