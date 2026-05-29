"""
뉴스 기사 & 논문 실시간 수집기 (News & Paper Real-time Collector)

무료 API와 RSS 피드를 활용하여 뉴스 기사와 학술 논문을 실시간으로 수집합니다.

지원 소스:
- 뉴스: NewsAPI, Google News RSS, Naver News RSS
- 논문: arXiv API, CrossRef API
- AI 처리: Claude (한국어 요약, 분류, 번역)
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


class ClaudeProcessor:
    """Claude LLM을 활용한 한국어 텍스트 처리 (요약, 분류, 번역)"""

    CATEGORIES = ["정치", "경제", "사회", "기술", "문화", "스포츠", "국제", "기타"]

    def __init__(self, api_key=None, model="claude-opus-4-8"):
        import anthropic
        self.model = model
        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )

    def _chat(self, system: str, user: str, max_tokens: int = 512) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        for block in response.content:
            if block.type == "text":
                return block.text.strip()
        return ""

    def summarize(self, text: str, max_chars: int = 150) -> str:
        if not text or not text.strip():
            return ""
        try:
            return self._chat(
                system="당신은 한국어 뉴스 요약 전문가입니다. 간결하고 명확한 한국어로 요약하세요.",
                user=f"다음 텍스트를 {max_chars}자 이내로 요약하세요:\n\n{text}",
                max_tokens=300,
            )
        except Exception as e:
            print(f"[Claude] 요약 오류: {e}")
            return text[:max_chars]

    def categorize(self, title: str, description: str = "") -> str:
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
            )
            return result if result in self.CATEGORIES else "기타"
        except Exception as e:
            print(f"[Claude] 분류 오류: {e}")
            return "기타"

    def translate_to_korean(self, text: str) -> str:
        if not text or not text.strip():
            return ""
        try:
            return self._chat(
                system="전문 번역가로서 주어진 영어 텍스트를 자연스러운 한국어로 번역하세요.",
                user=f"다음 텍스트를 한국어로 번역하세요:\n\n{text}",
                max_tokens=500,
            )
        except Exception as e:
            print(f"[Claude] 번역 오류: {e}")
            return text

    @staticmethod
    def _is_korean(text: str) -> bool:
        return any("가" <= c <= "힣" for c in text)

    def process_articles(self, articles: list, summarize: bool = True,
                         categorize: bool = False,
                         translate_titles: bool = False) -> list:
        processed = []
        total = len(articles)
        for i, article in enumerate(articles, 1):
            print(f"  [Claude] {i}/{total}: {article.get('title', '')[:40]}...")
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
            time.sleep(0.3)

        return processed


class AutonomousAgent:
    """Claude tool calling으로 스스로 검색 전략을 세우고 개선하는 자율 에이전트"""

    TOOLS = [
        {
            "name": "search_news",
            "description": "Google News RSS에서 뉴스 기사를 검색합니다.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색 키워드 (한국어 또는 영어)",
                    },
                    "lang": {
                        "type": "string",
                        "enum": ["ko", "en"],
                        "description": "검색 언어 (기본: ko)",
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "search_papers",
            "description": "arXiv에서 학술 논문을 검색합니다.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색 키워드 (영어 권장)",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "최대 결과 수 (기본: 5)",
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "finish",
            "description": "수집 완료. 최종 보고서를 저장하고 종료합니다.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "수집 결과 한국어 요약 보고서",
                    }
                },
                "required": ["summary"],
            },
        },
    ]

    def __init__(self, claude: ClaudeProcessor, news_collector: NewsCollector,
                 paper_collector: PaperCollector, output_dir: str = "collected_data"):
        self.claude = claude
        self.news_collector = news_collector
        self.paper_collector = paper_collector
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self._articles: list = []
        self._papers: list = []
        self._seen_links: set = set()

    def _call_tool(self, name: str, args: dict) -> str:
        if name == "search_news":
            query = args["query"]
            lang = args.get("lang", "ko")
            items = self.news_collector.collect_google_news_rss(query, lang=lang)
            new = [a for a in items if a.get("link") not in self._seen_links]
            for a in new:
                self._seen_links.add(a.get("link", ""))
            self._articles.extend(new)
            if not new:
                return f"'{query}' 검색: 새 기사 없음"
            titles = "\n".join(f"- {a['title']}" for a in new[:10])
            return f"'{query}' 검색 결과 {len(new)}건:\n{titles}"

        if name == "search_papers":
            query = args["query"]
            max_r = args.get("max_results", 5)
            items = self.paper_collector.collect_arxiv(query, max_results=max_r)
            new = [p for p in items if p.get("link") not in self._seen_links]
            for p in new:
                self._seen_links.add(p.get("link", ""))
            self._papers.extend(new)
            if not new:
                return f"'{query}' 논문 검색: 새 논문 없음"
            titles = "\n".join(f"- {p['title']}" for p in new[:5])
            return f"'{query}' 논문 {len(new)}건:\n{titles}"

        if name == "finish":
            return args.get("summary", "")

        return f"알 수 없는 도구: {name}"

    def run(self, goal: str, max_steps: int = 15) -> dict:
        """
        목표를 주면 Claude가 스스로 검색 전략을 세워 수집합니다.

        Args:
            goal: 수집 목표 (예: "최신 AI 반도체 뉴스와 논문 수집")
            max_steps: 최대 실행 단계 (무한 루프 방지)
        """
        import anthropic

        print(f"\n{'='*60}")
        print(f"  자율 에이전트 시작: {goal}")
        print(f"{'='*60}\n")

        system = (
            "당신은 뉴스와 논문을 수집하는 자율 에이전트입니다. "
            "주어진 목표를 위해 search_news와 search_papers 도구로 관련 정보를 수집하세요. "
            "검색 결과를 보고 더 구체적인 키워드로 추가 검색을 반복하며 정보를 확장하세요. "
            "충분한 정보가 모이면 finish를 호출해 한국어 요약 보고서를 작성하세요."
        )

        messages = [{"role": "user", "content": f"목표: {goal}"}]
        final_summary = ""

        for step in range(max_steps):
            print(f"[Agent 스텝 {step + 1}/{max_steps}]")
            try:
                response = self.claude.client.messages.create(
                    model=self.claude.model,
                    max_tokens=4096,
                    thinking={"type": "adaptive"},
                    system=system,
                    tools=self.TOOLS,
                    messages=messages,
                )
            except Exception as e:
                print(f"[Agent] API 오류: {e}")
                break

            # 응답을 메시지 히스토리에 추가
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                for block in response.content:
                    if block.type == "text":
                        final_summary = block.text
                        print(f"[Agent] 완료\n{final_summary}")
                break

            # tool_use 블록 처리
            tool_results = []
            done = False
            for block in response.content:
                if block.type != "tool_use":
                    continue

                print(f"  -> {block.name}({block.input})")
                result = self._call_tool(block.name, block.input)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

                if block.name == "finish":
                    final_summary = block.input.get("summary", "")
                    done = True

            messages.append({"role": "user", "content": tool_results})

            if done:
                print("\n[Agent] 수집 완료!")
                break

        self._save_results(final_summary)
        return {"articles": self._articles, "papers": self._papers, "summary": final_summary}

    def _save_results(self, summary: str) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        if self._articles:
            p = self.output_dir / f"agent_news_{ts}.json"
            p.write_text(
                json.dumps(self._articles, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"  뉴스 저장: {p} ({len(self._articles)}건)")
        if self._papers:
            p = self.output_dir / f"agent_papers_{ts}.json"
            p.write_text(
                json.dumps(self._papers, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"  논문 저장: {p} ({len(self._papers)}건)")
        if summary:
            p = self.output_dir / f"agent_report_{ts}.txt"
            p.write_text(summary, encoding="utf-8")
            print(f"  보고서 저장: {p}")
            print(f"\n{'='*60}\n  최종 보고서:\n{'='*60}\n{summary}")


class RealTimeCollector:
    """실시간 통합 수집기"""

    def __init__(self, newsapi_key=None, output_dir="collected_data",
                 claude_api_key=None, claude_model="claude-opus-4-8"):
        self.news_collector = NewsCollector(newsapi_key=newsapi_key)
        self.paper_collector = PaperCollector()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.collected_links = set()

        self.claude: ClaudeProcessor | None = None
        resolved_key = claude_api_key or os.environ.get("ANTHROPIC_API_KEY")
        if resolved_key:
            try:
                self.claude = ClaudeProcessor(api_key=resolved_key, model=claude_model)
                print(f"[Claude] 초기화 완료 (모델: {claude_model})")
            except Exception as e:
                print(f"[Claude] 초기화 실패: {e}")

    def _save_results(self, results, prefix):
        if not results:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.output_dir / f"{prefix}_{timestamp}.json"

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"  -> 저장 완료: {filename} ({len(results)}건)")
        return filename

    def _deduplicate(self, items):
        unique = []
        for item in items:
            link = item.get("link", "")
            if link and link not in self.collected_links:
                self.collected_links.add(link)
                unique.append(item)
        return unique

    def collect_news(self, queries, categories=None,
                     claude_summarize=False, claude_categorize=False,
                     claude_translate=False):
        all_articles = []

        for query in queries:
            all_articles.extend(self.news_collector.collect_google_news_rss(query))
            if self.news_collector.newsapi_key:
                all_articles.extend(self.news_collector.collect_newsapi(query))

        if categories:
            for cat in categories:
                all_articles.extend(self.news_collector.collect_naver_news_rss(cat))

        unique = self._deduplicate(all_articles)

        if unique and self.claude and (claude_summarize or claude_categorize or claude_translate):
            print(f"\n[Claude] {len(unique)}건 기사 한국어 처리 중...")
            unique = self.claude.process_articles(
                unique,
                summarize=claude_summarize,
                categorize=claude_categorize,
                translate_titles=claude_translate,
            )

        if unique:
            self._save_results(unique, "news")
        return unique

    def collect_papers(self, queries):
        all_papers = []

        for query in queries:
            all_papers.extend(self.paper_collector.collect_arxiv(query))
            all_papers.extend(self.paper_collector.collect_crossref(query))
            time.sleep(1)

        unique = self._deduplicate(all_papers)
        if unique:
            self._save_results(unique, "papers")
        return unique

    def collect_all(self, news_queries, paper_queries, news_categories=None,
                    claude_summarize=False, claude_categorize=False,
                    claude_translate=False):
        print(f"\n{'='*60}")
        print(f"  수집 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")

        print("\n[뉴스 수집 중...]")
        news = self.collect_news(
            news_queries, news_categories,
            claude_summarize=claude_summarize,
            claude_categorize=claude_categorize,
            claude_translate=claude_translate,
        )

        print("\n[논문 수집 중...]")
        papers = self.collect_papers(paper_queries)

        print(f"\n{'='*60}")
        print(f"  수집 완료! 뉴스: {len(news)}건, 논문: {len(papers)}건")
        print(f"{'='*60}\n")

        return {"news": news, "papers": papers}

    def start_scheduled(self, news_queries, paper_queries,
                        news_categories=None, interval_minutes=30,
                        claude_summarize=False, claude_categorize=False,
                        claude_translate=False):
        print(f"실시간 수집기 시작! (수집 주기: {interval_minutes}분)")
        print(f"뉴스 키워드: {news_queries}")
        print(f"논문 키워드: {paper_queries}")
        if self.claude:
            flags = [k for k, v in {
                "요약": claude_summarize,
                "분류": claude_categorize,
                "번역": claude_translate,
            }.items() if v]
            print(f"Claude 처리: {', '.join(flags) if flags else '비활성화'}")
        print("중지하려면 Ctrl+C를 누르세요.\n")

        self.collect_all(
            news_queries, paper_queries, news_categories,
            claude_summarize=claude_summarize,
            claude_categorize=claude_categorize,
            claude_translate=claude_translate,
        )

        schedule.every(interval_minutes).minutes.do(
            self.collect_all,
            news_queries, paper_queries, news_categories,
            claude_summarize, claude_categorize, claude_translate,
        )

        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n수집기가 중지되었습니다.")


def main():
    """사용 예시"""
    NEWSAPI_KEY = None
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
    CLAUDE_MODEL = "claude-opus-4-8"

    # ── 모드 선택 ──────────────────────────────────────────
    MODE = "agent"   # "agent" | "scheduled"
    # ──────────────────────────────────────────────────────

    if MODE == "agent":
        if not ANTHROPIC_API_KEY:
            print("ANTHROPIC_API_KEY 환경변수를 설정하세요.")
            return

        claude = ClaudeProcessor(api_key=ANTHROPIC_API_KEY, model=CLAUDE_MODEL)
        agent = AutonomousAgent(
            claude=claude,
            news_collector=NewsCollector(newsapi_key=NEWSAPI_KEY),
            paper_collector=PaperCollector(),
            output_dir="collected_data",
        )
        agent.run(
            goal="최신 AI 반도체 및 거대언어모델 뉴스와 논문을 수집하고 한국어로 요약하세요.",
            max_steps=15,
        )

    elif MODE == "scheduled":
        collector = RealTimeCollector(
            newsapi_key=NEWSAPI_KEY,
            output_dir="collected_data",
            claude_api_key=ANTHROPIC_API_KEY,
            claude_model=CLAUDE_MODEL,
        )
        collector.start_scheduled(
            news_queries=["인공지능", "AI"],
            paper_queries=["artificial intelligence", "large language model"],
            news_categories=["주요뉴스", "기술"],
            interval_minutes=30,
            claude_summarize=True,
            claude_categorize=True,
            claude_translate=True,
        )


if __name__ == "__main__":
    main()
