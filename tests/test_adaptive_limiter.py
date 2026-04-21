import asyncio

import httpx
import pytest
import respx

from item_scout.clients.http import (
    AdaptiveLimiter,
    build_http_client,
    request_with_backoff,
)


@pytest.mark.asyncio
async def test_limiter_reduces_rps_on_429():
    lim = AdaptiveLimiter(rps=10.0)
    assert lim.current_rps == 10.0
    await lim.on_throttle(retry_after=0.01)
    assert lim.current_rps == 5.0
    await asyncio.sleep(0.05)  # pause 해제
    await lim.acquire()  # 정상 통과


@pytest.mark.asyncio
@respx.mock
async def test_request_retries_on_429():
    url = "https://api.example.com/ping"
    route = respx.get(url).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0.01"}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    async with build_http_client(http2=False) as c:
        lim = AdaptiveLimiter(rps=100)
        r = await request_with_backoff(c, lim, "GET", url)
    assert r.status_code == 200
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_request_retries_on_5xx():
    url = "https://api.example.com/ping"
    route = respx.get(url).mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(503),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    async with build_http_client(http2=False) as c:
        lim = AdaptiveLimiter(rps=100)
        r = await request_with_backoff(c, lim, "GET", url, max_attempts=5)
    assert r.status_code == 200
    assert route.call_count == 3
