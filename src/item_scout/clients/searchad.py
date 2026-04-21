"""네이버 검색광고 API 클라이언트.

Docs: https://naver.github.io/searchad-apidoc/

인증 헤더:
  X-Timestamp : Unix ms
  X-API-KEY   : 액세스 라이선스
  X-Customer  : 광고주 customer id
  X-Signature : Base64(HMAC-SHA256(secret, f"{timestamp}.{method}.{uri}"))
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any

import httpx

from .http import AdaptiveLimiter, build_http_client, loads, request_with_backoff

BASE_URL = "https://api.searchad.naver.com"


def sign(timestamp_ms: str, method: str, uri: str, secret_key: str) -> str:
    msg = f"{timestamp_ms}.{method.upper()}.{uri}".encode()
    digest = hmac.new(secret_key.encode(), msg, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


@dataclass(slots=True)
class RelatedKeyword:
    keyword: str
    monthly_pc_qc: int
    monthly_mobile_qc: int
    monthly_ave_pc_clk: float
    monthly_ave_mobile_clk: float
    monthly_ave_pc_ctr: float
    monthly_ave_mobile_ctr: float
    pl_avg_depth: int
    comp_idx: str

    @property
    def total_qc(self) -> int:
        return self.monthly_pc_qc + self.monthly_mobile_qc

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> "RelatedKeyword":
        def _num(v: Any, typ: type) -> Any:
            if v in ("< 10", "<10", None, ""):
                return typ(5) if typ is int else typ(5.0)
            try:
                return typ(v)
            except (TypeError, ValueError):
                return typ(0)

        return cls(
            keyword=raw.get("relKeyword", ""),
            monthly_pc_qc=_num(raw.get("monthlyPcQcCnt"), int),
            monthly_mobile_qc=_num(raw.get("monthlyMobileQcCnt"), int),
            monthly_ave_pc_clk=_num(raw.get("monthlyAvePcClkCnt"), float),
            monthly_ave_mobile_clk=_num(raw.get("monthlyAveMobileClkCnt"), float),
            monthly_ave_pc_ctr=_num(raw.get("monthlyAvePcCtr"), float),
            monthly_ave_mobile_ctr=_num(raw.get("monthlyAveMobileCtr"), float),
            pl_avg_depth=_num(raw.get("plAvgDepth"), int),
            comp_idx=raw.get("compIdx", ""),
        )


class SearchAdClient:
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        customer_id: str,
        rps: float = 4.0,
        http: httpx.AsyncClient | None = None,
        http2: bool = True,
    ):
        self._api_key = api_key
        self._secret_key = secret_key
        self._customer_id = customer_id
        self._limiter = AdaptiveLimiter(rps=rps)
        self._http = http or build_http_client(base_url=BASE_URL, http2=http2)
        self._owns_http = http is None

    async def __aenter__(self) -> "SearchAdClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._owns_http:
            await self._http.aclose()

    def _headers(self, method: str, uri: str) -> dict[str, str]:
        ts = str(int(time.time() * 1000))
        return {
            "X-Timestamp": ts,
            "X-API-KEY": self._api_key,
            "X-Customer": self._customer_id,
            "X-Signature": sign(ts, method, uri, self._secret_key),
        }

    async def keywordstool(
        self,
        hint_keywords: list[str],
        *,
        show_detail: bool = True,
        include_hint: bool = True,
    ) -> list[RelatedKeyword]:
        """연관 키워드 + 월간 검색량. hint_keywords 최대 5개."""
        if not hint_keywords:
            return []
        if len(hint_keywords) > 5:
            raise ValueError("hint_keywords 는 최대 5개까지 허용됩니다.")
        uri = "/keywordstool"
        params = {
            "hintKeywords": ",".join(hint_keywords),
            "showDetail": "1" if show_detail else "0",
            "includeHintKeywords": "1" if include_hint else "0",
        }
        r = await request_with_backoff(
            self._http, self._limiter, "GET", uri,
            headers=self._headers("GET", uri), params=params,
        )
        data = loads(r.content)
        return [RelatedKeyword.from_api(x) for x in data.get("keywordList", [])]
