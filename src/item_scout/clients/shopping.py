"""네이버 쇼핑 검색 API 클라이언트.

Docs: https://developers.naver.com/docs/serviceapi/search/shopping/shopping.md
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .http import AdaptiveLimiter, build_http_client, loads, request_with_backoff

BASE_URL = "https://openapi.naver.com/v1/search/shop.json"


@dataclass(slots=True)
class ShoppingItem:
    title: str
    link: str
    lprice: int
    mall_name: str
    product_id: str
    product_type: str
    brand: str
    maker: str
    category1: str
    category2: str
    category3: str
    category4: str

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> "ShoppingItem":
        return cls(
            title=_strip_tags(raw.get("title", "")),
            link=raw.get("link", ""),
            lprice=int(raw.get("lprice") or 0),
            mall_name=raw.get("mallName", ""),
            product_id=str(raw.get("productId", "")),
            product_type=str(raw.get("productType", "")),
            brand=raw.get("brand", ""),
            maker=raw.get("maker", ""),
            category1=raw.get("category1", ""),
            category2=raw.get("category2", ""),
            category3=raw.get("category3", ""),
            category4=raw.get("category4", ""),
        )


@dataclass(slots=True)
class ShoppingSearchResult:
    query: str
    total: int
    items: list[ShoppingItem]


def _strip_tags(s: str) -> str:
    return s.replace("<b>", "").replace("</b>", "")


class ShoppingClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        rps: float = 8.0,
        http: httpx.AsyncClient | None = None,
        http2: bool = True,
    ):
        self._headers = {
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
        }
        self._limiter = AdaptiveLimiter(rps=rps)
        self._http = http or build_http_client(http2=http2)
        self._owns_http = http is None

    async def __aenter__(self) -> "ShoppingClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def search(
        self,
        query: str,
        *,
        display: int = 10,
        start: int = 1,
        sort: str = "sim",
    ) -> ShoppingSearchResult:
        params = {"query": query, "display": display, "start": start, "sort": sort}
        r = await request_with_backoff(
            self._http, self._limiter, "GET", BASE_URL,
            headers=self._headers, params=params,
        )
        data = loads(r.content)
        return ShoppingSearchResult(
            query=query,
            total=int(data.get("total", 0)),
            items=[ShoppingItem.from_api(i) for i in data.get("items", [])],
        )

    async def total_only(self, query: str) -> int:
        """대량 수집용: display=1 로 total 만."""
        res = await self.search(query, display=1)
        return res.total

    async def find_rank(self, query: str, product_id: str, max_pages: int = 10) -> int | None:
        for page in range(max_pages):
            start = 1 + page * 100
            if start > 1000:
                break
            res = await self.search(query, display=100, start=start)
            for idx, item in enumerate(res.items, start=start):
                if item.product_id == product_id:
                    return idx
            if not res.items:
                break
        return None
