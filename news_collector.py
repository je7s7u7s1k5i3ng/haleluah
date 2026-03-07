"""
뉴스 기사 & 논문 실시간 수집기 (News & Paper Real-time Collector)

무료 API와 RSS 피드를 활용하여 뉴스 기사와 학술 논문을 실시간으로 수집합니다.

지원 소스:
- 뉴스: NewsAPI, Google News RSS, Naver News RSS
- 논문: arXiv API, CrossRef API
"""

import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import requests
import schedule


class NewsCollector:
    """뉴스 기사 수집기"""

    def __init__(self, newsapi_key=None):
        self.newsapi_key = newsapi_key
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; NewsCollector/1.0)"
        })

    def collect_google_news_rss(self, query, lang="ko"):
        """Google News RSS에서 뉴스 수집 (API 키 불필요)"""
        encoded_query = quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl={lang}"

        articles = []
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)

            for item in root.findall(".//item"):
                article = {
                    "source": "Google News",
                    "title": item.findtext("title", ""),
                    "link": item.findtext("link", ""),
                    "published": item.findtext("pubDate", ""),
                    "description": item.findtext("description", ""),
                    "collected_at": datetime.now().isoformat(),
                }
                articles.append(article)

            print(f"[Google News] '{query}' 검색 결과: {len(articles)}건")
        except Exception as e:
            print(f"[Google News] 수집 오류: {e}")

        return articles

    def collect_naver_news_rss(self, category="주요뉴스"):
        """네이버 뉴스 RSS에서 뉴스 수집 (API 키 불필요)"""
        rss_urls = {
            "주요뉴스": "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko",
            "정치": "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRFZ4ZERBU0FtdHZLQUFQAQ?hl=ko&gl=KR",
            "경제": "https://news.google.com/rss/topics/CAAqIggKIhxDQkFTRHdvSkwyMHZNR2RtY0RFU0FtdHZLQUFQAQ?hl=ko&gl=KR",
            "사회": "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRFp0ZERBU0FtdHZLQUFQAQ?hl=ko&gl=KR",
            "기술": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtdHZHZ0pMVWlnQVAB?hl=ko&gl=KR",
        }
        url = rss_urls.get(category, rss_urls["주요뉴스"])

        articles = []
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)

            for item in root.findall(".//item"):
                article = {
                    "source": f"Google News KR ({category})",
                    "title": item.findtext("title", ""),
                    "link": item.findtext("link", ""),
                    "published": item.findtext("pubDate", ""),
                    "description": item.findtext("description", ""),
                    "collected_at": datetime.now().isoformat(),
                }
                articles.append(article)

            print(f"[한국 뉴스 - {category}] 수집 결과: {len(articles)}건")
        except Exception as e:
            print(f"[한국 뉴스] 수집 오류: {e}")

        return articles

    def collect_newsapi(self, query, language="ko", page_size=20):
        """NewsAPI에서 뉴스 수집 (무료 키 필요: https://newsapi.org)"""
        if not self.newsapi_key:
            print("[NewsAPI] API 키가 설정되지 않았습니다. https://newsapi.org 에서 무료 발급 가능")
            return []

        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "language": language,
            "pageSize": page_size,
            "sortBy": "publishedAt",
            "apiKey": self.newsapi_key,
        }

        articles = []
        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("articles", []):
                article = {
                    "source": f"NewsAPI - {item.get('source', {}).get('name', 'Unknown')}",
                    "title": item.get("title", ""),
                    "link": item.get("url", ""),
                    "published": item.get("publishedAt", ""),
                    "description": item.get("description", ""),
                    "author": item.get("author", ""),
                    "collected_at": datetime.now().isoformat(),
                }
                articles.append(article)

            print(f"[NewsAPI] '{query}' 검색 결과: {len(articles)}건")
        except Exception as e:
            print(f"[NewsAPI] 수집 오류: {e}")

        return articles


class PaperCollector:
    """학술 논문 수집기"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; PaperCollector/1.0)"
        })

    def collect_arxiv(self, query, max_results=20):
        """arXiv에서 논문 수집 (API 키 불필요)"""
        url = "http://export.arxiv.org/api/query"
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        papers = []
        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()

            ns = {"atom": "http://www.w3.org/2005/Atom"}
            root = ET.fromstring(resp.content)

            for entry in root.findall("atom:entry", ns):
                authors = [
                    a.find("atom:name", ns).text
                    for a in entry.findall("atom:author", ns)
                    if a.find("atom:name", ns) is not None
                ]
                categories = [
                    c.get("term", "")
                    for c in entry.findall("atom:category", ns)
                ]

                paper = {
                    "source": "arXiv",
                    "title": entry.findtext("atom:title", "", ns).strip().replace("\n", " "),
                    "authors": authors,
                    "abstract": entry.findtext("atom:summary", "", ns).strip().replace("\n", " "),
                    "link": entry.findtext("atom:id", "", ns),
                    "published": entry.findtext("atom:published", "", ns),
                    "updated": entry.findtext("atom:updated", "", ns),
                    "categories": categories,
                    "collected_at": datetime.now().isoformat(),
                }
                papers.append(paper)

            print(f"[arXiv] '{query}' 검색 결과: {len(papers)}건")
        except Exception as e:
            print(f"[arXiv] 수집 오류: {e}")

        return papers

    def collect_crossref(self, query, rows=20):
        """CrossRef에서 논문 수집 (API 키 불필요)"""
        url = "https://api.crossref.org/works"
        params = {
            "query": query,
            "rows": rows,
            "sort": "published",
            "order": "desc",
        }

        papers = []
        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("message", {}).get("items", []):
                authors = []
                for a in item.get("author", []):
                    name = f"{a.get('given', '')} {a.get('family', '')}".strip()
                    if name:
                        authors.append(name)

                paper = {
                    "source": "CrossRef",
                    "title": " ".join(item.get("title", [""])),
                    "authors": authors,
                    "doi": item.get("DOI", ""),
                    "link": item.get("URL", ""),
                    "published": str(item.get("published-print", item.get("created", {}))),
                    "journal": " ".join(item.get("container-title", [""])),
                    "type": item.get("type", ""),
                    "collected_at": datetime.now().isoformat(),
                }
                papers.append(paper)

            print(f"[CrossRef] '{query}' 검색 결과: {len(papers)}건")
        except Exception as e:
            print(f"[CrossRef] 수집 오류: {e}")

        return papers


class RealTimeCollector:
    """실시간 통합 수집기"""

    def __init__(self, newsapi_key=None, output_dir="collected_data"):
        self.news_collector = NewsCollector(newsapi_key=newsapi_key)
        self.paper_collector = PaperCollector()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.collected_links = set()  # 중복 방지

    def _save_results(self, results, prefix):
        """수집 결과를 JSON 파일로 저장"""
        if not results:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.output_dir / f"{prefix}_{timestamp}.json"

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"  -> 저장 완료: {filename} ({len(results)}건)")
        return filename

    def _deduplicate(self, items):
        """중복 제거"""
        unique = []
        for item in items:
            link = item.get("link", "")
            if link and link not in self.collected_links:
                self.collected_links.add(link)
                unique.append(item)
        return unique

    def collect_news(self, queries, categories=None):
        """뉴스 수집 (여러 키워드)"""
        all_articles = []

        for query in queries:
            all_articles.extend(self.news_collector.collect_google_news_rss(query))
            if self.news_collector.newsapi_key:
                all_articles.extend(self.news_collector.collect_newsapi(query))

        if categories:
            for cat in categories:
                all_articles.extend(self.news_collector.collect_naver_news_rss(cat))

        unique = self._deduplicate(all_articles)
        if unique:
            self._save_results(unique, "news")
        return unique

    def collect_papers(self, queries):
        """논문 수집 (여러 키워드)"""
        all_papers = []

        for query in queries:
            all_papers.extend(self.paper_collector.collect_arxiv(query))
            all_papers.extend(self.paper_collector.collect_crossref(query))
            time.sleep(1)  # API rate limit 준수

        unique = self._deduplicate(all_papers)
        if unique:
            self._save_results(unique, "papers")
        return unique

    def collect_all(self, news_queries, paper_queries, news_categories=None):
        """뉴스 + 논문 동시 수집"""
        print(f"\n{'='*60}")
        print(f"  수집 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")

        print("\n[뉴스 수집 중...]")
        news = self.collect_news(news_queries, news_categories)

        print("\n[논문 수집 중...]")
        papers = self.collect_papers(paper_queries)

        print(f"\n{'='*60}")
        print(f"  수집 완료! 뉴스: {len(news)}건, 논문: {len(papers)}건")
        print(f"{'='*60}\n")

        return {"news": news, "papers": papers}

    def start_scheduled(self, news_queries, paper_queries,
                        news_categories=None, interval_minutes=30):
        """스케줄 기반 주기적 수집"""
        print(f"실시간 수집기 시작! (수집 주기: {interval_minutes}분)")
        print(f"뉴스 키워드: {news_queries}")
        print(f"논문 키워드: {paper_queries}")
        print("중지하려면 Ctrl+C를 누르세요.\n")

        # 즉시 1회 수집
        self.collect_all(news_queries, paper_queries, news_categories)

        # 주기적 수집 스케줄 등록
        schedule.every(interval_minutes).minutes.do(
            self.collect_all, news_queries, paper_queries, news_categories
        )

        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n수집기가 중지되었습니다.")


def main():
    """사용 예시"""
    # --- 설정 ---
    NEWS_QUERIES = ["인공지능", "AI"]          # 뉴스 검색 키워드
    PAPER_QUERIES = ["artificial intelligence", "large language model"]  # 논문 검색 키워드
    NEWS_CATEGORIES = ["주요뉴스", "기술"]     # 한국 뉴스 카테고리
    NEWSAPI_KEY = None                         # (선택) https://newsapi.org 에서 무료 발급
    INTERVAL_MIN = 30                          # 수집 주기 (분)

    collector = RealTimeCollector(
        newsapi_key=NEWSAPI_KEY,
        output_dir="collected_data",
    )

    # 1회 수집
    # results = collector.collect_all(NEWS_QUERIES, PAPER_QUERIES, NEWS_CATEGORIES)

    # 실시간 주기적 수집
    collector.start_scheduled(
        news_queries=NEWS_QUERIES,
        paper_queries=PAPER_QUERIES,
        news_categories=NEWS_CATEGORIES,
        interval_minutes=INTERVAL_MIN,
    )


if __name__ == "__main__":
    main()
