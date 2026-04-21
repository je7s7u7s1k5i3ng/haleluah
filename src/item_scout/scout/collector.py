"""대량 수집기: 쇼핑 total + 검색광고 지표 결합."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Iterable
from dataclasses import dataclass

from ..clients.searchad import RelatedKeyword, SearchAdClient
from ..clients.shopping import ShoppingClient
from .analyzer import KeywordMetric
from .checkpoint import Checkpoint


@dataclass(slots=True)
class CollectStats:
    total: int = 0
    done: int = 0
    skipped: int = 0
    errors: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.total - self.done - self.skipped)


async def collect_related(
    ad: SearchAdClient, seeds: Iterable[str]
) -> dict[str, RelatedKeyword]:
    seeds = [s.strip() for s in seeds if s and s.strip()]
    out: dict[str, RelatedKeyword] = {}
    sem = asyncio.Semaphore(4)

    async def one(chunk: list[str]) -> list[RelatedKeyword]:
        async with sem:
            try:
                return await ad.keywordstool(chunk)
            except Exception:
                return []

    chunks = [seeds[i : i + 5] for i in range(0, len(seeds), 5)]
    results = await asyncio.gather(*(one(c) for c in chunks))
    for rels in results:
        for r in rels:
            out.setdefault(r.keyword, r)
    return out


async def expand_keywords(
    ad: SearchAdClient,
    seeds: Iterable[str],
    *,
    depth: int = 1,
    max_keywords: int = 5000,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict[str, RelatedKeyword]:
    """BFS 로 연관 키워드 확장."""
    pool: dict[str, RelatedKeyword] = {}
    frontier = sorted({s.strip() for s in seeds if s and s.strip()})
    for d in range(max(1, depth)):
        if not frontier or len(pool) >= max_keywords:
            break
        rels = await collect_related(ad, frontier[:200])
        new_keys = [k for k in rels if k not in pool]
        pool.update(rels)
        if on_progress:
            on_progress(d + 1, len(pool))
        if len(pool) >= max_keywords:
            break
        frontier = sorted(new_keys, key=lambda k: rels[k].total_qc, reverse=True)[:80]
    # max_keywords 컷
    if len(pool) > max_keywords:
        ranked = sorted(pool.values(), key=lambda r: r.total_qc, reverse=True)
        pool = {r.keyword: r for r in ranked[:max_keywords]}
    return pool


async def attach_product_counts(
    shop: ShoppingClient,
    related: dict[str, RelatedKeyword],
    *,
    concurrency: int = 20,
    checkpoint: Checkpoint | None = None,
    on_each: Callable[[KeywordMetric, CollectStats], None] | None = None,
) -> AsyncIterator[KeywordMetric]:
    """각 키워드의 쇼핑 total 을 동시성 제어로 조회 (스트림)."""
    sem = asyncio.Semaphore(concurrency)
    stats = CollectStats(total=len(related))
    queue: asyncio.Queue[KeywordMetric | None] = asyncio.Queue()

    async def worker(kw: str, rk: RelatedKeyword) -> None:
        if checkpoint and checkpoint.done(kw):
            stats.skipped += 1
            return
        async with sem:
            try:
                total = await shop.total_only(kw)
            except Exception:
                stats.errors += 1
                total = -1
        m = KeywordMetric(
            keyword=kw,
            total_products=max(total, 0),
            monthly_pc=rk.monthly_pc_qc,
            monthly_mobile=rk.monthly_mobile_qc,
            comp_idx=rk.comp_idx,
            pl_avg_depth=rk.pl_avg_depth,
        )
        stats.done += 1
        if checkpoint:
            checkpoint.mark(kw, {"total": total, "pc": rk.monthly_pc_qc, "mo": rk.monthly_mobile_qc})
        if on_each:
            on_each(m, stats)
        await queue.put(m)

    async def driver() -> None:
        tasks = [asyncio.create_task(worker(k, v)) for k, v in related.items()]
        await asyncio.gather(*tasks, return_exceptions=True)
        await queue.put(None)

    drv = asyncio.create_task(driver())
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
    finally:
        await drv
