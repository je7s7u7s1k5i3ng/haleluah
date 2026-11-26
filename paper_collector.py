"""
학술 논문 수집기 (Paper Collector)

API 키 없이 무료로 사용 가능한 논문 소스들:
- arXiv: 물리, 수학, CS, 통계 등 프리프린트
- PubMed: 의학/생명과학 논문
- Semantic Scholar: AI 기반 학술 검색
- CORE: 오픈액세스 논문 (영국)

기능:
- 논문 메타데이터 수집
- PDF 로컬 다운로드
- JSON으로 저장
"""

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import requests


class PaperCollector:
    """학술 논문 수집기 (API 키 불필요)"""

    def __init__(self, output_dir="papers"):
        self.output_dir = Path(output_dir)
        self.pdf_dir = self.output_dir / "pdfs"
        self.output_dir.mkdir(exist_ok=True)
        self.pdf_dir.mkdir(exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; PaperCollector/1.0; mailto:example@email.com)"
        })
        self.collected = []

    def _sanitize_filename(self, name):
        """파일명에 사용할 수 없는 문자 제거"""
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        name = name[:100]  # 파일명 길이 제한
        return name.strip()

    def _download_pdf(self, url, filename):
        """PDF 다운로드"""
        filepath = self.pdf_dir / f"{self._sanitize_filename(filename)}.pdf"

        if filepath.exists():
            print(f"    [건너뜀] 이미 존재: {filepath.name}")
            return str(filepath)

        try:
            resp = self.session.get(url, timeout=60, stream=True)
            resp.raise_for_status()

            with open(filepath, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"    [다운로드] {filepath.name}")
            return str(filepath)
        except Exception as e:
            print(f"    [실패] PDF 다운로드 오류: {e}")
            return None

    # ========== arXiv ==========
    def collect_arxiv(self, query, max_results=10, download_pdf=True):
        """
        arXiv에서 논문 수집
        - 물리학, 수학, 컴퓨터과학, 통계학 등
        - PDF 무료 다운로드 가능
        """
        print(f"\n[arXiv] '{query}' 검색 중...")

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
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()

            ns = {"atom": "http://www.w3.org/2005/Atom"}
            root = ET.fromstring(resp.content)

            for entry in root.findall("atom:entry", ns):
                # 저자 추출
                authors = [
                    a.find("atom:name", ns).text
                    for a in entry.findall("atom:author", ns)
                    if a.find("atom:name", ns) is not None
                ]

                # 카테고리 추출
                categories = [
                    c.get("term", "")
                    for c in entry.findall("atom:category", ns)
                ]

                # PDF 링크 찾기
                pdf_link = None
                for link in entry.findall("atom:link", ns):
                    if link.get("title") == "pdf":
                        pdf_link = link.get("href")
                        break

                arxiv_id = entry.findtext("atom:id", "", ns).split("/abs/")[-1]
                title = entry.findtext("atom:title", "", ns).strip().replace("\n", " ")

                paper = {
                    "source": "arXiv",
                    "id": arxiv_id,
                    "title": title,
                    "authors": authors,
                    "abstract": entry.findtext("atom:summary", "", ns).strip().replace("\n", " "),
                    "url": entry.findtext("atom:id", "", ns),
                    "pdf_url": pdf_link,
                    "published": entry.findtext("atom:published", "", ns),
                    "categories": categories,
                    "collected_at": datetime.now().isoformat(),
                }

                # PDF 다운로드
                if download_pdf and pdf_link:
                    paper["local_pdf"] = self._download_pdf(pdf_link, f"arxiv_{arxiv_id.replace('/', '_')}_{title[:50]}")

                papers.append(paper)

            print(f"[arXiv] 수집 완료: {len(papers)}건")
        except Exception as e:
            print(f"[arXiv] 오류: {e}")

        self.collected.extend(papers)
        return papers

    # ========== PubMed ==========
    def collect_pubmed(self, query, max_results=10):
        """
        PubMed에서 논문 수집
        - 의학, 생명과학 분야
        - 무료 API (NCBI E-utilities)
        """
        print(f"\n[PubMed] '{query}' 검색 중...")

        # 1단계: 검색하여 ID 목록 가져오기
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        search_params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "date",
        }

        papers = []
        try:
            resp = self.session.get(search_url, params=search_params, timeout=30)
            resp.raise_for_status()
            ids = resp.json().get("esearchresult", {}).get("idlist", [])

            if not ids:
                print("[PubMed] 검색 결과 없음")
                return papers

            # 2단계: 상세 정보 가져오기
            fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            fetch_params = {
                "db": "pubmed",
                "id": ",".join(ids),
                "retmode": "xml",
            }

            time.sleep(0.5)  # API rate limit
            resp = self.session.get(fetch_url, params=fetch_params, timeout=30)
            resp.raise_for_status()

            root = ET.fromstring(resp.content)

            for article in root.findall(".//PubmedArticle"):
                # 제목
                title_elem = article.find(".//ArticleTitle")
                title = "".join(title_elem.itertext()) if title_elem is not None else ""

                # 저자
                authors = []
                for author in article.findall(".//Author"):
                    lastname = author.findtext("LastName", "")
                    forename = author.findtext("ForeName", "")
                    if lastname:
                        authors.append(f"{forename} {lastname}".strip())

                # 초록
                abstract_parts = []
                for abs_text in article.findall(".//AbstractText"):
                    text = "".join(abs_text.itertext())
                    if text:
                        abstract_parts.append(text)
                abstract = " ".join(abstract_parts)

                # PMID
                pmid = article.findtext(".//PMID", "")

                # 출판 날짜
                pub_date = article.find(".//PubDate")
                if pub_date is not None:
                    year = pub_date.findtext("Year", "")
                    month = pub_date.findtext("Month", "")
                    day = pub_date.findtext("Day", "")
                    published = f"{year}-{month}-{day}".strip("-")
                else:
                    published = ""

                # 저널명
                journal = article.findtext(".//Journal/Title", "")

                # DOI
                doi = ""
                for aid in article.findall(".//ArticleId"):
                    if aid.get("IdType") == "doi":
                        doi = aid.text
                        break

                paper = {
                    "source": "PubMed",
                    "id": pmid,
                    "title": title,
                    "authors": authors,
                    "abstract": abstract,
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    "doi": doi,
                    "journal": journal,
                    "published": published,
                    "collected_at": datetime.now().isoformat(),
                }
                papers.append(paper)

            print(f"[PubMed] 수집 완료: {len(papers)}건")
        except Exception as e:
            print(f"[PubMed] 오류: {e}")

        self.collected.extend(papers)
        return papers

    # ========== Semantic Scholar ==========
    def collect_semantic_scholar(self, query, max_results=10):
        """
        Semantic Scholar에서 논문 수집
        - AI 기반 학술 검색
        - 모든 분야
        - 무료 (rate limit 있음)
        """
        print(f"\n[Semantic Scholar] '{query}' 검색 중...")

        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": max_results,
            "fields": "paperId,title,authors,abstract,url,year,citationCount,openAccessPdf",
        }

        papers = []
        try:
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("data", []):
                authors = [a.get("name", "") for a in item.get("authors", [])]

                # 오픈액세스 PDF
                oa_pdf = item.get("openAccessPdf")
                pdf_url = oa_pdf.get("url") if oa_pdf else None

                paper = {
                    "source": "Semantic Scholar",
                    "id": item.get("paperId", ""),
                    "title": item.get("title", ""),
                    "authors": authors,
                    "abstract": item.get("abstract", ""),
                    "url": item.get("url", ""),
                    "pdf_url": pdf_url,
                    "year": item.get("year"),
                    "citations": item.get("citationCount", 0),
                    "collected_at": datetime.now().isoformat(),
                }

                # PDF 다운로드
                if pdf_url:
                    paper["local_pdf"] = self._download_pdf(
                        pdf_url,
                        f"s2_{item.get('paperId', '')[:10]}_{item.get('title', '')[:50]}"
                    )

                papers.append(paper)

            print(f"[Semantic Scholar] 수집 완료: {len(papers)}건")
        except Exception as e:
            print(f"[Semantic Scholar] 오류: {e}")

        self.collected.extend(papers)
        time.sleep(1)  # Rate limit 준수
        return papers

    # ========== CrossRef ==========
    def collect_crossref(self, query, max_results=10):
        """
        CrossRef에서 논문 수집
        - DOI 기반 메타데이터
        - 모든 분야
        """
        print(f"\n[CrossRef] '{query}' 검색 중...")

        url = "https://api.crossref.org/works"
        params = {
            "query": query,
            "rows": max_results,
            "sort": "published",
            "order": "desc",
        }

        papers = []
        try:
            resp = self.session.get(url, params=params, timeout=30)
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
                    "id": item.get("DOI", ""),
                    "title": " ".join(item.get("title", [""])),
                    "authors": authors,
                    "doi": item.get("DOI", ""),
                    "url": item.get("URL", ""),
                    "journal": " ".join(item.get("container-title", [""])),
                    "published": str(item.get("published-print", item.get("created", {}))),
                    "type": item.get("type", ""),
                    "collected_at": datetime.now().isoformat(),
                }
                papers.append(paper)

            print(f"[CrossRef] 수집 완료: {len(papers)}건")
        except Exception as e:
            print(f"[CrossRef] 오류: {e}")

        self.collected.extend(papers)
        return papers

    # ========== 저장 ==========
    def save_results(self, filename=None):
        """수집 결과를 JSON으로 저장"""
        if not self.collected:
            print("\n저장할 논문이 없습니다.")
            return None

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"papers_{timestamp}.json"

        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.collected, f, ensure_ascii=False, indent=2)

        print(f"\n저장 완료: {filepath} ({len(self.collected)}건)")
        return filepath

    def get_summary(self):
        """수집 결과 요약"""
        if not self.collected:
            return "수집된 논문이 없습니다."

        sources = {}
        for p in self.collected:
            src = p.get("source", "Unknown")
            sources[src] = sources.get(src, 0) + 1

        pdf_count = sum(1 for p in self.collected if p.get("local_pdf"))

        summary = [
            f"\n{'='*50}",
            f"  수집 결과 요약",
            f"{'='*50}",
            f"  총 논문 수: {len(self.collected)}건",
            f"  다운로드된 PDF: {pdf_count}건",
            f"  소스별:",
        ]
        for src, count in sources.items():
            summary.append(f"    - {src}: {count}건")
        summary.append(f"{'='*50}\n")

        return "\n".join(summary)


def main():
    """사용 예시"""
    collector = PaperCollector(output_dir="papers")

    # 검색 키워드
    query = "large language model"

    # 각 소스에서 수집 (원하는 것만 선택)
    collector.collect_arxiv(query, max_results=5, download_pdf=True)
    collector.collect_semantic_scholar(query, max_results=5)
    collector.collect_pubmed(query, max_results=5)
    collector.collect_crossref(query, max_results=5)

    # 결과 저장 및 요약
    collector.save_results()
    print(collector.get_summary())


if __name__ == "__main__":
    main()
