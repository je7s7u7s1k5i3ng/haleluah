"""대량 수집기: 쇼핑 total + 검색광고 지표를 합쳐 KeywordMetric 생성."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable

from ..clients.searchad import RelatedKeyword, SearchAdClient
from ..clients.shopping import ShoppingClient
from .analyzer import KeywordMetric


async def collect_related(
    ad: SearchAdClient, seeds: Iterable[str]
) -> dict[str, RelatedKeyword]:
    """시드를 5개씩 묶어 /keywordstool 호출. 중복 제거한 dict 반환."""
    seeds = [s.strip() for s in seeds if s and s.strip()]
    out: dict[str, RelatedKeyword] = {}
    for i in range(0, len(seeds), 5):
        chunk = seeds[i : i + 5]
        rels = await ad.keywordstool(chunk)
        for r in rels:
            out.setdefault(r.keyword, r)
    return out


async def expand_keywords(
    ad: SearchAdClient,
    seeds: Iterable[str],
    *,
    depth: int = 1,
    max_keywords: int = 5000,
) -> dict[str, RelatedKeyword]:
    """BFS 로 연관 키워드 확장. depth=2 면 시드→연관→재연관."""
    pool: dict[str, RelatedKeyword] = {}
    frontier = list({s.strip() for s in seeds if s and s.strip()})
    for _ in range(max(1, depth)):
        if not frontier or len(pool) >= max_keywords:
            break
        rels = await collect_related(ad, frontier[:100])
        new_keys = [k for k in rels if k not in pool]
        pool.update(rels)
        if len(pool) >= max_keywords:
            break
        frontier = sorted(
            new_keys,
            key=lambda k: rels[k].total_qc,
            reverse=True,
        )[:50]
    return dict(list(pool.items())[:max_keywords])


async def attach_product_counts(
    shop: ShoppingClient,
    related: dict[str, RelatedKeyword],
    *,
    concurrency: int = 10,
) -> list[KeywordMetric]:
    """각 키워드의 쇼핑 API total 을 동시성 제한으로 조회."""
    sem = asyncio.Semaphore(concurrency)

    async def one(kw: str, rk: RelatedKeyword) -> KeywordMetric:
        async with sem:
            try:
                total = await shop.total_only(kw)
            except Exception:
                total = 0
        return KeywordMetric(
            keyword=kw,
            total_products=total,
            monthly_pc=rk.monthly_pc_qc,
            monthly_mobile=rk.monthly_mobile_qc,
            comp_idx=rk.comp_idx,
            pl_avg_depth=rk.pl_avg_depth,
        )

    tasks = [one(k, v) for k, v in related.items()]
    return await asyncio.gather(*tasks)
