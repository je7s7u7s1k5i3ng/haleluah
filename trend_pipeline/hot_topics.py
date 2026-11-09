"""
오늘 터지는 주제 측정

신호 (모두 숫자):
- S_articles : 최근 24시간 같은 사건 기사 수
- S_outlets  : 같은 사건을 다룬 서로 다른 매체 수 (동시 보도)
- S_burst    : 핵심 단어 오늘 보도량 / 지난 7일 하루 평균 (기록이 쌓여야 계산, 없으면 HOLD)
- S_search   : 네이버 데이터랩 검색량 최근 3일 / 이전 평균 (키 있을 때만, 없으면 HOLD)

측정 못 한 신호는 0점이 아니라 HOLD로 두고 나머지 가중치로 다시 나눈다.
"""

import collections
import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import requests

from .config import CATEGORIES, GNEWS_KR
from .textutil import clean_title, jaccard, numbers, shared, tokens

WEIGHTS = {"S_articles": 0.25, "S_outlets": 0.35, "S_burst": 0.25, "S_search": 0.15}
FRESH_HOURS = 24


class HotTopicFinder:
    def __init__(self, store, settings, session=None, log=print):
        self.store = store
        self.settings = settings
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", "Mozilla/5.0 (compatible; TrendPipeline/1.0)")
        self.log = log
        self.signal_status = {}

    # ---------- 수집 ----------
    def _fetch_rss(self, url):
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            return ET.fromstring(resp.content).findall(".//item")
        except Exception as e:
            self.log(f"[뉴스] 수집 실패 {url[:80]}: {e}")
            return None

    def collect_articles(self, category, now=None):
        now = now or datetime.now(timezone.utc)
        conf = CATEGORIES[category]
        urls = list(conf["topic_feeds"])
        for seed in conf["seeds"]:
            urls.append(f"https://news.google.com/rss/search?q={quote(seed + ' when:1d')}&{GNEWS_KR}")
        articles, seen, ok = [], set(), 0
        for url in urls:
            items = self._fetch_rss(url)
            if items is None:
                continue
            ok += 1
            for it in items:
                title, outlet = clean_title(it.findtext("title", ""))
                src = it.find("source")
                if src is not None and (src.text or "").strip():
                    outlet = src.text.strip()
                try:
                    published = parsedate_to_datetime(it.findtext("pubDate", ""))
                except (TypeError, ValueError):
                    continue
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
                age_h = (now - published).total_seconds() / 3600
                if age_h > FRESH_HOURS or age_h < -1:
                    continue  # FRESH_HOURS 넘은 기사는 '터지는' 근거에서 제외
                key = (title, outlet)
                if key in seen:
                    continue
                seen.add(key)
                articles.append({
                    "title": title, "outlet": outlet or "알수없음",
                    "link": it.findtext("link", ""), "published": published.isoformat(),
                    "age_hours": round(age_h, 1), "tokens": tokens(title),
                })
            time.sleep(self.settings.get("request_sleep_sec", 1.0))
        self.signal_status["news_feeds"] = f"{ok}/{len(urls)} 성공"
        return articles

    # ---------- 같은 사건 묶기 ----------
    @staticmethod
    def cluster(articles, threshold=0.25, min_shared=2):
        """같은 사건 묶기: 핵심어 2개 이상 공유 또는 자카드 유사도 0.25 이상."""
        clusters = []
        for a in sorted(articles, key=lambda x: x["age_hours"]):
            best, best_sim = None, (0, 0.0)
            for c in clusters:
                sim = (shared(a["tokens"], c["token_pool"]), jaccard(a["tokens"], c["token_pool"]))
                if sim > best_sim:
                    best, best_sim = c, sim
            if best and (best_sim[0] >= min_shared or best_sim[1] >= threshold):
                best["articles"].append(a)
                best["token_counter"].update(set(a["tokens"]))
                best["token_pool"] = [t for t, _ in best["token_counter"].most_common(8)]
            else:
                clusters.append({
                    "articles": [a],
                    "token_counter": collections.Counter(set(a["tokens"])),
                    "token_pool": list(a["tokens"]),
                })
        return clusters

    # ---------- 네이버 데이터랩 (선택) ----------
    def naver_search_ratio(self, keyword, today):
        cid, secret = self.settings.get("naver_client_id"), self.settings.get("naver_client_secret")
        if not (cid and secret):
            return None
        body = {
            "startDate": (today - timedelta(days=30)).strftime("%Y-%m-%d"),
            "endDate": today.strftime("%Y-%m-%d"),
            "timeUnit": "date",
            "keywordGroups": [{"groupName": keyword, "keywords": [keyword]}],
        }
        try:
            resp = self.session.post(
                "https://openapi.naver.com/v1/datalab/search",
                headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret,
                         "Content-Type": "application/json"},
                data=json.dumps(body), timeout=15,
            )
            resp.raise_for_status()
            data = [d["ratio"] for d in resp.json()["results"][0]["data"]]
        except Exception as e:
            self.log(f"[데이터랩] '{keyword}' 실패: {e}")
            return None
        if len(data) < 7:
            return None
        recent = sum(data[-3:]) / 3
        before = sum(data[:-3]) / max(len(data) - 3, 1)
        return round(recent / before, 2) if before > 0 else None

    # ---------- 점수 ----------
    def find(self, category, top_n=5, now=None):
        now = now or datetime.now(timezone.utc)
        day = now.astimezone(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
        articles = self.collect_articles(category, now)
        clusters = self.cluster(articles)

        # 오늘 단어 보도량 기록 (다음 회차의 급상승 기준선)
        day_counts = collections.Counter()
        for a in articles:
            day_counts.update(set(a["tokens"]))
        self.store.save_token_counts(day, category, day_counts)

        topics = []
        for c in clusters:
            arts = c["articles"]
            outlets = {a["outlet"] for a in arts}
            if len(arts) < 2:
                continue  # 기사 1건짜리는 '터지는 주제' 후보에서 제외
            common = [t for t, _ in c["token_counter"].most_common(4)]
            # 숫자 표현(1450원·3%)은 뒤로: 주제 이름·유튜브 검색어는 단어가 먼저 와야 잘 걸린다
            keywords = sorted(common, key=lambda t: t[0].isdigit())[:3]
            head = keywords[0]
            base = self.store.baseline(day, category, head, days=self.settings.get("lookback_days", 7))
            burst = round(day_counts[head] / (base + 1), 2) if base is not None else None
            topics.append({
                "label": " ".join(keywords),
                "keywords": keywords,
                "S_articles": len(arts),
                "S_outlets": len(outlets),
                "S_burst": burst,
                "S_search": None,
                "outlets": sorted(outlets),
                "median_age_hours": sorted(a["age_hours"] for a in arts)[len(arts) // 2],
                "headlines": [a["title"] for a in arts[:8]],
                "links": [a["link"] for a in arts[:8]],
                "news_numbers": sorted({n for a in arts for n in numbers(a["title"])}),
            })

        # 상위 후보만 데이터랩 조회 (호출 수 절약)
        topics.sort(key=lambda t: (t["S_outlets"], t["S_articles"]), reverse=True)
        for t in topics[: top_n * 2]:
            t["S_search"] = self.naver_search_ratio(t["keywords"][0], now.date())

        self._score(topics)
        topics.sort(key=lambda t: t["hot_score"], reverse=True)
        self.signal_status["S_burst"] = "OK" if any(t["S_burst"] is not None for t in topics) else "HOLD(기록 쌓이는 중 — 2회차부터 계산)"
        self.signal_status["S_search"] = "OK" if any(t["S_search"] is not None for t in topics) else "HOLD(네이버 데이터랩 키 없음 또는 실패)"
        self.signal_status["articles_24h"] = len(articles)
        return topics[:top_n]

    @staticmethod
    def _score(topics):
        maxima = {k: max((t[k] for t in topics if t[k] is not None), default=0) for k in WEIGHTS}
        for t in topics:
            total, wsum, parts = 0.0, 0.0, {}
            for k, w in WEIGHTS.items():
                if t[k] is None or maxima[k] == 0:
                    parts[k] = "HOLD"
                    continue
                v = t[k] / maxima[k]
                parts[k] = round(v, 2)
                total += w * v
                wsum += w
            t["hot_score"] = round(100 * total / wsum, 1) if wsum else 0.0
            t["score_parts"] = parts
