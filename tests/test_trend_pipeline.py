"""trend_pipeline 전 구간 테스트 — 네트워크 없이 가짜 응답으로 돈다."""

import io
import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import pytest
from PIL import Image

from trend_pipeline import analyze, run
from trend_pipeline.hot_topics import HotTopicFinder
from trend_pipeline.store import Store
from trend_pipeline.textutil import clean_title, numbers, tokens
from trend_pipeline.transcripts import parse_vtt
from trend_pipeline.youtube import iso_duration_sec

NOW = datetime(2026, 11, 9, 3, 0, tzinfo=timezone.utc)


def rss(items):
    body = "".join(
        f"<item><title>{t}</title><link>https://n.example/{i}</link>"
        f"<pubDate>{format_datetime(NOW - timedelta(hours=h))}</pubDate><source>{o}</source></item>"
        for i, (t, o, h) in enumerate(items)
    )
    return f"<rss><channel>{body}</channel></rss>".encode()


NEWS = rss([
    ("환율 1,450원 돌파…외환당국 긴급 점검 - 한국경제", "한국경제", 2),
    ("환율 1,450원 넘어 연중 최고…수입물가 비상 - 매일경제", "매일경제", 3),
    ("원·달러 환율 1,450원 돌파, 당국 구두개입 - 연합뉴스", "연합뉴스", 1),
    ("코스피 3% 급락, 외국인 매도 폭탄 - 서울경제", "서울경제", 4),
    ("코스피 3% 급락…반도체 약세 - 머니투데이", "머니투데이", 5),
    ("동네 빵집 신메뉴 출시 - 지역신문", "지역신문", 6),
    ("지난주 오래된 기사 - 옛날신문", "옛날신문", 60),
])


class FakeResp:
    def __init__(self, content=b"", status=200, data=None):
        self.content = content
        self.status_code = status
        self._data = data
        self.text = content.decode("utf-8", "ignore") if content else json.dumps(data or {})

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._data


def thumb_bytes(color):
    buf = io.BytesIO()
    Image.new("RGB", (64, 36), color).save(buf, "JPEG")
    return buf.getvalue()


class FakeSession:
    """뉴스 RSS + 유튜브 API 흉내. 주제마다 영상 10개."""

    def __init__(self, quota_after=None):
        self.headers = {}
        self.calls = 0
        self.quota_after = quota_after

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        if "news.google.com" in url:
            return FakeResp(NEWS)
        if "googleapis.com/youtube" in url:
            if self.quota_after is not None and self.calls > self.quota_after:
                return FakeResp(b'{"error":{"errors":[{"reason":"quotaExceeded"}]}}', status=403)
            if url.endswith("/search"):
                q = params["q"].replace(" ", "")
                return FakeResp(data={"items": [{"id": {"videoId": f"{q}{i}"}} for i in range(10)]})
            if url.endswith("/videos"):
                items = []
                for i, vid in enumerate(params["id"].split(",")):
                    items.append({
                        "id": vid,
                        "snippet": {
                            "title": ("환율 1,450원 터졌다 지금 사야 할까?" if i < 3 else f"경제 뉴스 정리 {i}"),
                            "description": "환율 분석", "channelId": f"ch{i}", "channelTitle": f"채널{i}",
                            "publishedAt": (NOW - timedelta(hours=10 + i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "thumbnails": {"high": {"url": f"https://i.ytimg.com/{vid}.jpg"}},
                        },
                        "statistics": {"viewCount": str(100000 if i < 3 else 2000), "likeCount": "100", "commentCount": "10"},
                        "contentDetails": {"duration": "PT8M30S" if i % 2 else "PT45S"},
                    })
                return FakeResp(data={"items": items})
            if url.endswith("/channels"):
                return FakeResp(data={"items": [{"id": c, "statistics": {"subscriberCount": "10000"}}
                                                for c in params["id"].split(",")]})
        if "ytimg.com" in url:
            return FakeResp(thumb_bytes((250, 30, 30) if url.split("/")[-1][-5] in "012" else (90, 90, 90)))
        return FakeResp(status=404)

    def post(self, *a, **k):
        return FakeResp(status=401)


# ---------- 단위 ----------
def test_clean_title_and_tokens():
    title, outlet = clean_title("[속보] 환율 1,450원 돌파 - 한국경제")
    assert title == "환율 1,450원 돌파" and outlet == "한국경제"
    assert "환율" in tokens("환율이 크게 올랐다")
    assert "1450원" in numbers(title)


def test_iso_duration():
    assert iso_duration_sec("PT1H2M3S") == 3723
    assert iso_duration_sec("PT45S") == 45
    assert iso_duration_sec("bad") is None


def test_parse_vtt_merges_repeats():
    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\n환율이 <c>터졌습니다</c>\n\n" \
          "00:00:03.000 --> 00:00:05.000\n환율이 터졌습니다\n\n00:00:20.000 --> 00:00:22.000\n지금 사야 할까요?\n"
    cues = parse_vtt(vtt)
    assert cues == [(1.0, "환율이 터졌습니다"), (20.0, "지금 사야 할까요?")]


def test_hot_topics_cluster_and_hold(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    finder = HotTopicFinder(store, {"request_sleep_sec": 0}, session=FakeSession(), log=lambda m: None)
    topics = finder.find("경제", top_n=5, now=NOW)
    labels = [t["label"] for t in topics]
    assert any("환율" in l for l in labels)
    top = topics[0]
    assert top["S_outlets"] == 3 and top["S_articles"] == 3     # 환율 3개 매체
    assert all("빵집" not in l for l in labels)                  # 기사 1건짜리 제외
    assert all("오래된" not in h for t in topics for h in t["headlines"])  # 24시간 초과 제외
    assert top["S_burst"] is None and top["score_parts"]["S_burst"] == "HOLD"  # 첫 회차는 기준선 없음
    assert "1450원" in top["news_numbers"]


def test_burst_after_history(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    store.save_token_counts("2026-11-08", "경제", {"환율": 1, "코스피": 2})
    finder = HotTopicFinder(store, {"request_sleep_sec": 0}, session=FakeSession(), log=lambda m: None)
    topics = finder.find("경제", top_n=5, now=NOW)
    fx = next(t for t in topics if "환율" in t["label"])
    assert fx["S_burst"] is not None and fx["S_burst"] > 1


def test_hit_analysis_needs_sample():
    recs = [{"outlier_ratio": i, "title_len": i} for i in range(5)]
    assert "표본 부족" in analyze.hit_analysis(recs)["status"]


def test_cross_check_flags_clickbait():
    topic = {"keywords": ["환율", "1,450원"], "news_numbers": ["1,450원"]}
    rec = {"title": "환율 폭등 지금 사야 할까", "description": ""}
    cues = [(1.0, "오늘은 날씨 이야기"), (70.0, "환율 1,450원")]
    cc = analyze.cross_check(rec, topic, cues)
    assert cc["topic_in_title"] and cc["news_numbers_in_script"] == "1/1"
    assert "제목 약속이 첫 60초에 안 나옴" in cc["flags"]


# ---------- 전 구간 ----------
def test_end_to_end_with_youtube(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "dummy")
    out = run.main(["오늘", "경제", "터진", "주제로", "수집해줘", "--base-dir", str(tmp_path),
                    "--no-transcripts", "--top-topics", "2"], session=FakeSession(), now=NOW)
    assert out.parent == tmp_path / "결과"
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["category"] == "경제" and manifest["videos"] == 20
    assert manifest["state"] == "CANDIDATE"
    report = (out / "보고서.md").read_text(encoding="utf-8")
    assert "터진 영상 vs 나머지" in report and "🔥" in report
    assert len(list((out / "thumbnails").glob("*.jpg"))) == 20
    rows = [json.loads(l) for l in (out / "videos.jsonl").read_text(encoding="utf-8").splitlines()]
    hits = [r for r in rows if r.get("is_hit")]
    assert hits and all(r["views"] == 100000 for r in hits)
    assert (tmp_path / "data" / "trend_history.sqlite").exists()
    assert list((tmp_path / "logs").glob("*.log"))


def test_without_key_news_only_and_quota(tmp_path, monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    out = run.main(["--category", "경제", "--base-dir", str(tmp_path)], session=FakeSession(), now=NOW)
    status = json.loads((out / "manifest.json").read_text(encoding="utf-8"))["status"]
    assert status["유튜브"].startswith("HOLD")

    monkeypatch.setenv("YOUTUBE_API_KEY", "dummy")
    out2 = run.main(["--category", "경제", "--base-dir", str(tmp_path), "--no-transcripts"],
                    session=FakeSession(quota_after=12), now=NOW + timedelta(minutes=1))
    status2 = json.loads((out2 / "manifest.json").read_text(encoding="utf-8"))["status"]
    assert "할당량" in status2["유튜브"]


def test_unknown_category_errors(tmp_path):
    with pytest.raises(SystemExit):
        run.main(["오늘", "날씨", "--base-dir", str(tmp_path)], session=FakeSession(), now=NOW)
