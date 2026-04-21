"""네이버 데이터랩 쇼핑인사이트 API 클라이언트.

Docs: https://developers.naver.com/docs/serviceapi/datalab/shopping/shopping.md
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from .http import AdaptiveLimiter, build_http_client, loads, request_with_backoff

BASE_URL = "https://openapi.naver.com/v1/datalab/shopping"


@dataclass(slots=True)
class TrendPoint:
    period: str
    ratio: float
    group: str | None = None


@dataclass(slots=True)
class TrendResult:
    title: str
    keywords: list[str]
    data: list[TrendPoint]


class DataLabClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        rps: float = 4.0,
        http: httpx.AsyncClient | None = None,
        http2: bool = True,
    ):
        self._headers = {
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
            "Content-Type": "application/json",
        }
        self._limiter = AdaptiveLimiter(rps=rps)
        self._http = http or build_http_client(base_url=BASE_URL, http2=http2)
        self._owns_http = http is None

    async def __aenter__(self) -> "DataLabClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        r = await request_with_backoff(
            self._http, self._limiter, "POST", path,
            headers=self._headers, json=payload,
        )
        return loads(r.content)

    async def category_keywords_trend(
        self,
        category: str,
        keywords: list[tuple[str, list[str]]],
        start: date,
        end: date,
        time_unit: str = "month",
        device: str | None = None,
        ages: list[str] | None = None,
        gender: str | None = None,
    ) -> list[TrendResult]:
        payload: dict[str, Any] = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "timeUnit": time_unit,
            "category": category,
            "keyword": [{"name": name, "param": params} for name, params in keywords],
        }
        if device:
            payload["device"] = device
        if ages:
            payload["ages"] = ages
        if gender:
            payload["gender"] = gender
        data = await self._post("/category/keywords", payload)
        return [
            TrendResult(
                title=res.get("title", ""),
                keywords=res.get("keywords", []),
                data=[
                    TrendPoint(period=p["period"], ratio=float(p["ratio"]))
                    for p in res.get("data", [])
                ],
            )
            for res in data.get("results", [])
        ]

    async def category_trend(
        self,
        categories: list[tuple[str, list[str]]],
        start: date,
        end: date,
        time_unit: str = "month",
    ) -> list[TrendResult]:
        """카테고리(복수) 트렌드 비교."""
        payload = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "timeUnit": time_unit,
            "category": [{"name": n, "param": p} for n, p in categories],
        }
        data = await self._post("/categories", payload)
        return [
            TrendResult(
                title=res.get("title", ""),
                keywords=res.get("keywords", []),
                data=[
                    TrendPoint(period=p["period"], ratio=float(p["ratio"]))
                    for p in res.get("data", [])
                ],
            )
            for res in data.get("results", [])
        ]
