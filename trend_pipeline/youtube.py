"""
유튜브 공식 Data API v3로 주제별 영상 메타데이터·썸네일 수집

할당량(하루 기본 10,000단위): search 100 / videos·channels 1.
주제 5개 × 검색 1회 ≈ 510단위. 할당량 초과(403 quotaExceeded)면 즉시 멈추고 HOLD로 기록한다.
"""

import re
import time
from datetime import datetime, timedelta, timezone

import requests

API = "https://www.googleapis.com/youtube/v3"
_DUR = re.compile(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


class QuotaExceeded(Exception):
    pass


def iso_duration_sec(value):
    m = _DUR.fullmatch(value or "")
    if not m:
        return None
    d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


class YouTubeCollector:
    def __init__(self, api_key, settings, session=None, log=print):
        self.api_key = api_key
        self.settings = settings
        self.session = session or requests.Session()
        self.log = log
        self.units_used = 0

    def _get(self, endpoint, cost, **params):
        params["key"] = self.api_key
        resp = self.session.get(f"{API}/{endpoint}", params=params, timeout=20)
        self.units_used += cost
        if resp.status_code == 403 and "quota" in resp.text.lower():
            raise QuotaExceeded(resp.text[:200])
        resp.raise_for_status()
        return resp.json()

    def search(self, query, max_results=10, days=7, now=None):
        now = now or datetime.now(timezone.utc)
        after = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        data = self._get(
            "search", 100, part="snippet", q=query, type="video", regionCode="KR",
            relevanceLanguage="ko", order="viewCount", publishedAfter=after,
            maxResults=max_results,
        )
        return [it["id"]["videoId"] for it in data.get("items", []) if it.get("id", {}).get("videoId")]

    def videos(self, ids):
        if not ids:
            return []
        data = self._get("videos", 1, part="snippet,statistics,contentDetails", id=",".join(ids))
        return data.get("items", [])

    def channels(self, ids):
        out = {}
        ids = list(dict.fromkeys(ids))
        for i in range(0, len(ids), 50):
            data = self._get("channels", 1, part="statistics", id=",".join(ids[i:i + 50]))
            for it in data.get("items", []):
                st = it.get("statistics", {})
                out[it["id"]] = None if st.get("hiddenSubscriberCount") else int(st.get("subscriberCount", 0))
        return out

    @staticmethod
    def best_thumbnail(snippet):
        thumbs = snippet.get("thumbnails", {})
        for key in ("maxres", "standard", "high", "medium", "default"):
            if key in thumbs:
                return thumbs[key]["url"]
        return None

    def download(self, url, path):
        try:
            resp = self.session.get(url, timeout=20)
            resp.raise_for_status()
            path.write_bytes(resp.content)
            return True
        except Exception as e:
            self.log(f"[썸네일] 실패 {url}: {e}")
            return False

    def collect_topic(self, topic, thumb_dir, now=None):
        """주제 1개 → 영상 레코드 목록."""
        now = now or datetime.now(timezone.utc)
        query = " ".join(topic["keywords"][:2])
        ids = self.search(query, self.settings.get("videos_per_topic", 10),
                          self.settings.get("lookback_days", 7), now)
        items = self.videos(ids)
        subs = self.channels([it["snippet"]["channelId"] for it in items])
        records = []
        for it in items:
            sn, st, cd = it["snippet"], it.get("statistics", {}), it.get("contentDetails", {})
            published = datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00"))
            rec = {
                "topic": topic["label"],
                "video_id": it["id"],
                "url": f"https://www.youtube.com/watch?v={it['id']}",
                "title": sn.get("title", ""),
                "description": sn.get("description", ""),
                "tags": sn.get("tags", []),
                "channel_id": sn.get("channelId"),
                "channel_title": sn.get("channelTitle", ""),
                "published": sn["publishedAt"],
                "age_hours": round((now - published).total_seconds() / 3600, 1),
                "duration_sec": iso_duration_sec(cd.get("duration")),
                "views": int(st["viewCount"]) if "viewCount" in st else None,
                "likes": int(st["likeCount"]) if "likeCount" in st else None,
                "comments": int(st["commentCount"]) if "commentCount" in st else None,
                "subscribers": subs.get(sn.get("channelId")),
                "thumbnail_url": self.best_thumbnail(sn),
                "thumbnail_file": None,
            }
            if rec["thumbnail_url"]:
                path = thumb_dir / f"{it['id']}.jpg"
                if self.download(rec["thumbnail_url"], path):
                    rec["thumbnail_file"] = str(path)
            records.append(rec)
            time.sleep(self.settings.get("request_sleep_sec", 1.0) / 4)
        return records
