"""네이버 데이터랩 쇼핑인사이트 API 클라이언트.

Docs: https://developers.naver.com/docs/serviceapi/datalab/shopping/shopping.md
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx
from aiolimiter import AsyncLimiter
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

BASE_URL = "https://openapi.naver.com/v1/datalab/shopping"


@dataclass(slots=True)
class TrendPoint:
    period: str
    ratio: float


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
    ):
        self._headers = {
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
            "Content-Type": "application/json",
        }
        self._limiter = AsyncLimiter(max_rate=rps, time_period=1.0)
        self._http = http or httpx.AsyncClient(base_url=BASE_URL, timeout=15.0)
        self._owns_http = http is None

    async def __aenter__(self) -> "DataLabClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._owns_http:
            await self._http.aclose()

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        reraise=True,
    )
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
        """카테고리 내 키워드 트렌드 비교."""
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

        async with self._limiter:
            r = await self._http.post(
                "/category/keywords", headers=self._headers, json=payload
            )
            r.raise_for_status()
        data = r.json()
        results = []
        for res in data.get("results", []):
            results.append(
                TrendResult(
                    title=res.get("title", ""),
                    keywords=res.get("keywords", []),
                    data=[
                        TrendPoint(period=p["period"], ratio=float(p["ratio"]))
                        for p in res.get("data", [])
                    ],
                )
            )
        return results
