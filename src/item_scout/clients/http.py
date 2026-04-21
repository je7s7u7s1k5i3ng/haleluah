"""공용 HTTP 클라이언트 팩토리 + 적응형 레이트리미터."""
from __future__ import annotations

import asyncio
import random
import time

import httpx
import orjson
from aiolimiter import AsyncLimiter


def build_http_client(
    *,
    base_url: str = "",
    http2: bool = True,
    timeout: float = 15.0,
    max_connections: int = 40,
) -> httpx.AsyncClient:
    """공용 AsyncClient. HTTP/2 + 커넥션 풀 + orjson 파싱 친화."""
    limits = httpx.Limits(
        max_connections=max_connections,
        max_keepalive_connections=max_connections,
        keepalive_expiry=30.0,
    )
    return httpx.AsyncClient(
        base_url=base_url,
        http2=http2,
        timeout=httpx.Timeout(timeout, connect=5.0),
        limits=limits,
    )


def loads(data: bytes) -> dict:
    return orjson.loads(data)


class AdaptiveLimiter:
    """토큰버킷 + 429/Retry-After 적응형 backoff.

    - 평상시: aiolimiter 로 RPS 제한
    - 429 수신 시: Retry-After 만큼 전역 pause 후 RPS 50% 감속
    - 일정 시간 429 없으면 점진적 RPS 복원
    """

    def __init__(self, rps: float, max_rps: float | None = None):
        self._base_rps = rps
        self._max_rps = max_rps or rps
        self._current_rps = rps
        self._limiter = AsyncLimiter(max_rate=rps, time_period=1.0)
        self._pause_until = 0.0
        self._last_throttle_ts = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            now = time.monotonic()
            if now < self._pause_until:
                await asyncio.sleep(self._pause_until - now + random.uniform(0, 0.1))
                continue
            # 1분 무사고면 10% 씩 복원 (base_rps 상한)
            if (
                self._current_rps < self._base_rps
                and now - self._last_throttle_ts > 60
            ):
                async with self._lock:
                    self._current_rps = min(self._base_rps, self._current_rps * 1.1)
                    self._limiter = AsyncLimiter(
                        max_rate=self._current_rps, time_period=1.0
                    )
                    self._last_throttle_ts = now
            break
        await self._limiter.acquire()

    async def on_throttle(self, retry_after: float | None) -> None:
        """429 수신 시 호출."""
        async with self._lock:
            self._pause_until = time.monotonic() + (retry_after or 5.0)
            self._current_rps = max(0.5, self._current_rps * 0.5)
            self._limiter = AsyncLimiter(max_rate=self._current_rps, time_period=1.0)
            self._last_throttle_ts = time.monotonic()

    @property
    def current_rps(self) -> float:
        return self._current_rps


async def request_with_backoff(
    client: httpx.AsyncClient,
    limiter: AdaptiveLimiter,
    method: str,
    url: str,
    *,
    max_attempts: int = 5,
    **kwargs,
) -> httpx.Response:
    """429 인식 + 지수 backoff 재시도."""
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        await limiter.acquire()
        try:
            r = await client.request(method, url, **kwargs)
        except (httpx.TransportError, httpx.ReadTimeout) as e:
            last_exc = e
            await asyncio.sleep(min(8, 0.5 * 2**attempt) + random.uniform(0, 0.3))
            continue
        if r.status_code == 429:
            ra = r.headers.get("Retry-After")
            retry = float(ra) if ra and ra.replace(".", "", 1).isdigit() else None
            await limiter.on_throttle(retry)
            continue
        if 500 <= r.status_code < 600:
            await asyncio.sleep(min(8, 0.5 * 2**attempt) + random.uniform(0, 0.3))
            continue
        r.raise_for_status()
        return r
    if last_exc:
        raise last_exc
    raise RuntimeError(f"{method} {url} 실패: 최대 재시도 초과")
