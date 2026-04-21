"""Item Scout CLI."""
from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

import pandas as pd
import typer
from rich.console import Console
from rich.table import Table

from .clients.datalab import DataLabClient
from .clients.searchad import SearchAdClient
from .clients.shopping import ShoppingClient
from .config import get_settings
from .scout.analyzer import KeywordMetric, filter_golden
from .scout.collector import attach_product_counts, collect_related, expand_keywords
from .storage.db import Storage

app = typer.Typer(help="네이버 API 기반 키워드 스카우트")
console = Console()


def _render(metrics: list[KeywordMetric], title: str = "결과") -> None:
    table = Table(title=title, show_lines=False)
    for col in [
        "키워드",
        "상품수",
        "PC검색",
        "모바일",
        "총검색",
        "경쟁강도",
        "황금점수",
        "등급",
    ]:
        table.add_column(col, justify="right" if col != "키워드" else "left")
    for m in metrics:
        comp = "∞" if m.competition == float("inf") else f"{m.competition:.3f}"
        table.add_row(
            m.keyword,
            f"{m.total_products:,}",
            f"{m.monthly_pc:,}",
            f"{m.monthly_mobile:,}",
            f"{m.total_qc:,}",
            comp,
            f"{m.golden_score:.1f}",
            m.grade,
        )
    console.print(table)


@app.command()
def search(keyword: str):
    """단일 키워드 진단 (쇼핑 + 검색광고)."""
    settings = get_settings()
    settings.require_shopping()
    settings.require_searchad()

    async def run() -> KeywordMetric:
        async with (
            ShoppingClient(settings.naver_client_id, settings.naver_client_secret) as s,
            SearchAdClient(
                settings.searchad_api_key,
                settings.searchad_secret_key,
                settings.searchad_customer_id,
            ) as a,
        ):
            total_task = asyncio.create_task(s.total_only(keyword))
            rels = await a.keywordstool([keyword])
            total = await total_task
        rk = next((r for r in rels if r.keyword == keyword.replace(" ", "").upper()), None)
        rk = rk or (rels[0] if rels else None)
        return KeywordMetric(
            keyword=keyword,
            total_products=total,
            monthly_pc=rk.monthly_pc_qc if rk else 0,
            monthly_mobile=rk.monthly_mobile_qc if rk else 0,
            comp_idx=rk.comp_idx if rk else "",
            pl_avg_depth=rk.pl_avg_depth if rk else 0,
        )

    metric = asyncio.run(run())
    Storage(settings.scout_db_path).save_metrics([metric])
    _render([metric], title=f"'{keyword}' 진단")


@app.command()
def expand(
    seed: str,
    depth: int = typer.Option(1, min=1, max=3),
    max_keywords: int = typer.Option(500, "--max"),
):
    """연관 키워드 확장만 (쇼핑 total 미조회, 빠름)."""
    settings = get_settings()
    settings.require_searchad()

    async def run():
        async with SearchAdClient(
            settings.searchad_api_key,
            settings.searchad_secret_key,
            settings.searchad_customer_id,
        ) as a:
            return await expand_keywords(
                a, [seed], depth=depth, max_keywords=max_keywords
            )

    pool = asyncio.run(run())
    table = Table(title=f"'{seed}' 연관 키워드 ({len(pool)}개)")
    for col in ["키워드", "PC검색", "모바일", "총검색", "경쟁정도"]:
        table.add_column(col, justify="right" if col != "키워드" else "left")
    for rk in sorted(pool.values(), key=lambda r: r.total_qc, reverse=True)[:100]:
        table.add_row(
            rk.keyword,
            f"{rk.monthly_pc_qc:,}",
            f"{rk.monthly_mobile_qc:,}",
            f"{rk.total_qc:,}",
            rk.comp_idx,
        )
    console.print(table)


@app.command()
def mine(
    seeds_file: Path = typer.Argument(..., help="시드 키워드 목록 (한 줄에 하나)"),
    min_vol: int = typer.Option(500, help="최소 월 총검색수"),
    max_comp: float = typer.Option(1.0, help="최대 경쟁강도"),
    max_products: int = typer.Option(0, help="최대 상품수 (0=제한없음)"),
    depth: int = typer.Option(1, min=1, max=3),
    max_keywords: int = typer.Option(2000, "--max"),
    out: Path = typer.Option(Path("gold.xlsx"), help="결과 엑셀 경로"),
):
    """시드에서 황금키워드 대량 채굴."""
    settings = get_settings()
    settings.require_shopping()
    settings.require_searchad()

    seeds = [ln.strip() for ln in seeds_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not seeds:
        raise typer.BadParameter("시드 파일이 비어있습니다.")

    async def run() -> list[KeywordMetric]:
        async with (
            SearchAdClient(
                settings.searchad_api_key,
                settings.searchad_secret_key,
                settings.searchad_customer_id,
                rps=settings.scout_rps_searchad,
            ) as a,
            ShoppingClient(
                settings.naver_client_id,
                settings.naver_client_secret,
                rps=settings.scout_rps_shopping,
            ) as s,
        ):
            console.print(f"[bold]1/3[/] 연관 키워드 확장 (depth={depth})")
            related = await expand_keywords(
                a, seeds, depth=depth, max_keywords=max_keywords
            )
            console.print(f"  → {len(related):,} 키워드")
            console.print("[bold]2/3[/] 쇼핑 상품수 수집")
            metrics = await attach_product_counts(
                s, related, concurrency=settings.scout_concurrency
            )
        return metrics

    metrics = asyncio.run(run())
    console.print("[bold]3/3[/] 필터링 + 저장")
    Storage(settings.scout_db_path).save_metrics(metrics)
    gold = filter_golden(
        metrics,
        min_vol=min_vol,
        max_comp=max_comp,
        max_products=max_products or None,
    )
    df = pd.DataFrame([m.to_row() for m in gold])
    df.to_excel(out, index=False)
    console.print(f"[green]황금키워드 {len(gold)}개 → {out}[/]")
    _render(gold[:30], title="상위 30개")


@app.command()
def track(
    product_id: str,
    keyword: str = typer.Option(..., "--keyword", "-k"),
    max_pages: int = typer.Option(10, min=1, max=10),
):
    """특정 productId 의 키워드 노출 순위 추적."""
    settings = get_settings()
    settings.require_shopping()

    async def run() -> int | None:
        async with ShoppingClient(
            settings.naver_client_id, settings.naver_client_secret
        ) as s:
            return await s.find_rank(keyword, product_id, max_pages=max_pages)

    rank = asyncio.run(run())
    Storage(settings.scout_db_path).save_rank(product_id, keyword, rank)
    if rank is None:
        console.print(f"[yellow]'{keyword}' 상위 {max_pages*100}위 내 미노출[/]")
    else:
        console.print(f"[green]'{keyword}' → {rank}위[/]")


@app.command()
def trend(
    keyword: str,
    category: str = typer.Option("50000000", help="쇼핑 카테고리 코드"),
    days: int = typer.Option(90, min=7, max=365),
    period: str = typer.Option("week", help="date|week|month"),
):
    """데이터랩 쇼핑인사이트 키워드 트렌드."""
    settings = get_settings()
    settings.require_shopping()

    async def run():
        async with DataLabClient(
            settings.naver_client_id, settings.naver_client_secret
        ) as d:
            return await d.category_keywords_trend(
                category=category,
                keywords=[(keyword, [keyword])],
                start=date.today().fromordinal(date.today().toordinal() - days),
                end=date.today(),
                time_unit=period,
            )

    results = asyncio.run(run())
    for res in results:
        table = Table(title=f"{res.title} 트렌드")
        table.add_column("기간")
        table.add_column("비율", justify="right")
        for p in res.data:
            table.add_row(p.period, f"{p.ratio:.2f}")
        console.print(table)


if __name__ == "__main__":
    app()
