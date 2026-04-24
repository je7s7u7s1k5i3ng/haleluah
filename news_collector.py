"""
뉴스 기사 & 논문 실시간 수집기 (News & Paper Real-time Collector)

무료 API와 RSS 피드를 활용하여 뉴스 기사와 학술 논문을 실시간으로 수집합니다.

지원 소스:
- 뉴스: NewsAPI, Google News RSS, Naver News RSS
- 논문: arXiv API, CrossRef API
- AI 처리: Qwen (한국어 요약, 분류, 번역)
"""

import json
import os
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

    @staticmethod
    def _parse_xml_safe(content: bytes) -> ET.Element:
        """한글 등 멀티바이트 문자가 포함된 XML을 안전하게 파싱"""
        try:
            return ET.fromstring(content)
        except ET.ParseError:
            # BOM 또는 잘못된 헤더 제거 후 UTF-8로 재시도
            text = content.decode("utf-8", errors="replace")
            text = text.lstrip("﻿")
            return ET.fromstring(text.encode("utf-8"))

    def collect_google_news_rss(self, query, lang="ko"):
        """Google News RSS에서 뉴스 수집 (API 키 불필요)"""
        encoded_query = quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl={lang}"

        articles = []
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            root = self._parse_xml_safe(resp.content)

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
            root = self._parse_xml_safe(resp.content)

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


class QwenProcessor:
    """Qwen LLM을 활용한 한국어 텍스트 처리 (요약, 분류, 번역)"""

    CATEGORIES = ["정치", "경제", "사회", "기술", "문화", "스포츠", "국제", "기타"]

    def __init__(self, api_key=None, model="qwen-plus",
                 base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"):
        """
        Args:
            api_key: DashScope API 키. 없으면 DASHSCOPE_API_KEY 환경변수를 사용.
            model: 사용할 Qwen 모델 ("qwen-turbo" / "qwen-plus" / "qwen-max")
            base_url: OpenAI 호환 엔드포인트
        """
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError(
                "Qwen 사용을 위해 'openai' 패키지가 필요합니다: pip install openai"
            ) from exc

        resolved_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
        if not resolved_key:
            raise ValueError(
                "Qwen API 키가 필요합니다. "
                "DASHSCOPE_API_KEY 환경변수를 설정하거나 api_key 인자를 전달하세요."
            )

        self.model = model
        self.client = OpenAI(api_key=resolved_key, base_url=base_url)

    def _chat(self, system: str, user: str, max_tokens: int = 512,
              temperature: float = 0.3) -> str:
        """공통 채팅 호출 (UTF-8 응답 보장)"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        # content는 이미 str이지만 bytes로 돌아오는 경우 대비
        content = response.choices[0].message.content or ""
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        return content.strip()

    def summarize(self, text: str, max_chars: int = 150) -> str:
        """한국어 텍스트 요약"""
        if not text or not text.strip():
            return ""
        try:
            return self._chat(
                system="당신은 한국어 뉴스 요약 전문가입니다. 간결하고 명확한 한국어로 요약하세요.",
                user=f"다음 텍스트를 {max_chars}자 이내로 요약하세요:\n\n{text}",
                max_tokens=300,
            )
        except Exception as e:
            print(f"[Qwen] 요약 오류: {e}")
            return text[:max_chars]

    def categorize(self, title: str, description: str = "") -> str:
        """한국어 뉴스 카테고리 분류"""
        body = f"제목: {title}"
        if description:
            body += f"\n내용: {description[:300]}"
        try:
            result = self._chat(
                system=(
                    "당신은 한국어 뉴스 분류 전문가입니다. "
                    f"다음 카테고리 중 하나만 답하세요: {', '.join(self.CATEGORIES)}"
                ),
                user=body,
                max_tokens=10,
                temperature=0.0,
            )
            # 응답이 목록에 없으면 기타 반환
            return result if result in self.CATEGORIES else "기타"
        except Exception as e:
            print(f"[Qwen] 분류 오류: {e}")
            return "기타"

    def translate_to_korean(self, text: str) -> str:
        """영어 → 한국어 번역"""
        if not text or not text.strip():
            return ""
        try:
            return self._chat(
                system="전문 번역가로서 주어진 영어 텍스트를 자연스러운 한국어로 번역하세요.",
                user=f"다음 텍스트를 한국어로 번역하세요:\n\n{text}",
                max_tokens=500,
            )
        except Exception as e:
            print(f"[Qwen] 번역 오류: {e}")
            return text

    @staticmethod
    def _is_korean(text: str) -> bool:
        return any("가" <= c <= "힣" for c in text)

    def process_articles(self, articles: list, summarize: bool = True,
                         categorize: bool = False,
                         translate_titles: bool = False) -> list:
        """뉴스 기사 목록에 Qwen 처리 결과 추가"""
        processed = []
        total = len(articles)
        for i, article in enumerate(articles, 1):
            print(f"  [Qwen] {i}/{total}: {article.get('title', '')[:40]}...")
            item = article.copy()

            desc = item.get("description", "")
            title = item.get("title", "")

            if summarize and desc:
                item["summary_ko"] = self.summarize(desc)

            if categorize:
                item["category"] = self.categorize(title, desc)

            if translate_titles and title and not self._is_korean(title):
                item["title_ko"] = self.translate_to_korean(title)

            processed.append(item)
            time.sleep(0.5)  # Rate limit 준수

        return processed


class RealTimeCollector:
    """실시간 통합 수집기"""

    def __init__(self, newsapi_key=None, output_dir="collected_data",
                 qwen_api_key=None, qwen_model="qwen-plus"):
        self.news_collector = NewsCollector(newsapi_key=newsapi_key)
        self.paper_collector = PaperCollector()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.collected_links = set()  # 중복 방지

        # Qwen 프로세서 (API 키가 있을 때만 초기화)
        self.qwen: QwenProcessor | None = None
        resolved_key = qwen_api_key or os.environ.get("DASHSCOPE_API_KEY")
        if resolved_key:
            try:
                self.qwen = QwenProcessor(api_key=resolved_key, model=qwen_model)
                print(f"[Qwen] 초기화 완료 (모델: {qwen_model})")
            except Exception as e:
                print(f"[Qwen] 초기화 실패: {e}")

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

    def collect_news(self, queries, categories=None,
                     qwen_summarize=False, qwen_categorize=False,
                     qwen_translate=False):
        """뉴스 수집 (여러 키워드)

        Args:
            queries: 검색 키워드 목록
            categories: 한국 뉴스 카테고리 목록
            qwen_summarize: Qwen으로 한국어 요약 추가
            qwen_categorize: Qwen으로 카테고리 자동 분류
            qwen_translate: Qwen으로 영어 제목 한국어 번역
        """
        all_articles = []

        for query in queries:
            all_articles.extend(self.news_collector.collect_google_news_rss(query))
            if self.news_collector.newsapi_key:
                all_articles.extend(self.news_collector.collect_newsapi(query))

        if categories:
            for cat in categories:
                all_articles.extend(self.news_collector.collect_naver_news_rss(cat))

        unique = self._deduplicate(all_articles)

        if unique and self.qwen and (qwen_summarize or qwen_categorize or qwen_translate):
            print(f"\n[Qwen] {len(unique)}건 기사 한국어 처리 중...")
            unique = self.qwen.process_articles(
                unique,
                summarize=qwen_summarize,
                categorize=qwen_categorize,
                translate_titles=qwen_translate,
            )

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

    def collect_all(self, news_queries, paper_queries, news_categories=None,
                    qwen_summarize=False, qwen_categorize=False,
                    qwen_translate=False):
        """뉴스 + 논문 동시 수집"""
        print(f"\n{'='*60}")
        print(f"  수집 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")

        print("\n[뉴스 수집 중...]")
        news = self.collect_news(
            news_queries, news_categories,
            qwen_summarize=qwen_summarize,
            qwen_categorize=qwen_categorize,
            qwen_translate=qwen_translate,
        )

        print("\n[논문 수집 중...]")
        papers = self.collect_papers(paper_queries)

        print(f"\n{'='*60}")
        print(f"  수집 완료! 뉴스: {len(news)}건, 논문: {len(papers)}건")
        print(f"{'='*60}\n")

        return {"news": news, "papers": papers}

    def start_scheduled(self, news_queries, paper_queries,
                        news_categories=None, interval_minutes=30,
                        qwen_summarize=False, qwen_categorize=False,
                        qwen_translate=False):
        """스케줄 기반 주기적 수집"""
        print(f"실시간 수집기 시작! (수집 주기: {interval_minutes}분)")
        print(f"뉴스 키워드: {news_queries}")
        print(f"논문 키워드: {paper_queries}")
        if self.qwen:
            flags = [k for k, v in {
                "요약": qwen_summarize,
                "분류": qwen_categorize,
                "번역": qwen_translate,
            }.items() if v]
            print(f"Qwen 처리: {', '.join(flags) if flags else '비활성화'}")
        print("중지하려면 Ctrl+C를 누르세요.\n")

        # 즉시 1회 수집
        self.collect_all(
            news_queries, paper_queries, news_categories,
            qwen_summarize=qwen_summarize,
            qwen_categorize=qwen_categorize,
            qwen_translate=qwen_translate,
        )

        # 주기적 수집 스케줄 등록
        schedule.every(interval_minutes).minutes.do(
            self.collect_all,
            news_queries, paper_queries, news_categories,
            qwen_summarize, qwen_categorize, qwen_translate,
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

    # Qwen 설정 (선택): DASHSCOPE_API_KEY 환경변수 또는 아래에 직접 입력
    # 모델 선택: "qwen-turbo" (빠름/저렴) | "qwen-plus" (균형) | "qwen-max" (고성능)
    QWEN_API_KEY = os.environ.get("DASHSCOPE_API_KEY")  # 또는 직접 문자열 입력
    QWEN_MODEL = "qwen-plus"

    collector = RealTimeCollector(
        newsapi_key=NEWSAPI_KEY,
        output_dir="collected_data",
        qwen_api_key=QWEN_API_KEY,
        qwen_model=QWEN_MODEL,
    )

    # 1회 수집 (Qwen 한국어 처리 포함)
    # results = collector.collect_all(
    #     NEWS_QUERIES, PAPER_QUERIES, NEWS_CATEGORIES,
    #     qwen_summarize=True,   # 한국어 요약 추가
    #     qwen_categorize=True,  # 카테고리 자동 분류
    #     qwen_translate=True,   # 영어 제목 한국어 번역
    # )

    # 실시간 주기적 수집
    collector.start_scheduled(
        news_queries=NEWS_QUERIES,
        paper_queries=PAPER_QUERIES,
        news_categories=NEWS_CATEGORIES,
        interval_minutes=INTERVAL_MIN,
        qwen_summarize=True,   # 한국어 요약
        qwen_categorize=True,  # 카테고리 분류
        qwen_translate=True,   # 영어 제목 번역
    )


if __name__ == "__main__":
    main()
