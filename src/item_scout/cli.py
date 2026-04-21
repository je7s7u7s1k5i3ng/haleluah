"""Item Scout CLI."""
from __future__ import annotations

import asyncio
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import typer
from rich.console import Console
from rich.live import Live
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from .clients.datalab import DataLabClient
from .clients.searchad import SearchAdClient
from .clients.shopping import ShoppingClient
from .config import get_settings
from .scout.analyzer import KeywordMetric, filter_golden
from .scout.category_codes import CATEGORIES, resolve
from .scout.checkpoint import Checkpoint
from .scout.collector import (
    CollectStats,
    attach_product_counts,
    collect_related,
    expand_keywords,
)
from .storage.db import Storage

app = typer.Typer(help="네이버 API 기반 키워드 스카우트 (대량 수집 지원)")
console = Console()


def _render(metrics: list[KeywordMetric], title: str = "결과") -> None:
    table = Table(title=title, show_lines=False)
    for col, just in [
        ("키워드", "left"),
        ("상품수", "right"),
        ("PC검색", "right"),
        ("모바일", "right"),
        ("총검색", "right"),
        ("경쟁강도", "right"),
        ("황금점수", "right"),
        ("등급", "center"),
    ]:
        table.add_column(col, justify=just)
    for m in metrics:
        comp = "∞" if m.competition == float("inf") else f"{m.competition:.3f}"
        grade_color = {"S": "bold magenta", "A": "bold green", "B": "cyan", "C": "white", "D": "dim"}[m.grade]
        table.add_row(
            m.keyword,
            f"{m.total_products:,}",
            f"{m.monthly_pc:,}",
            f"{m.monthly_mobile:,}",
            f"{m.total_qc:,}",
            comp,
            f"{m.golden_score:,.1f}",
            f"[{grade_color}]{m.grade}[/]",
        )
    console.print(table)


def _progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("/"),
        TimeRemainingColumn(),
        console=console,
    )


@app.command()
def search(keyword: str):
    """단일 키워드 진단 (쇼핑 + 검색광고)."""
    s = get_settings()
    s.require_shopping()
    s.require_searchad()

    async def run() -> KeywordMetric:
        async with (
            ShoppingClient(s.naver_client_id, s.naver_client_secret, http2=s.scout_http2) as shop,
            SearchAdClient(s.searchad_api_key, s.searchad_secret_key, s.searchad_customer_id, http2=s.scout_http2) as ad,
        ):
            total_task = asyncio.create_task(shop.total_only(keyword))
            rels = await ad.keywordstool([keyword])
            total = await total_task
        rk = rels[0] if rels else None
        return KeywordMetric(
            keyword=keyword,
            total_products=total,
            monthly_pc=rk.monthly_pc_qc if rk else 0,
            monthly_mobile=rk.monthly_mobile_qc if rk else 0,
            comp_idx=rk.comp_idx if rk else "",
            pl_avg_depth=rk.pl_avg_depth if rk else 0,
        )

    metric = asyncio.run(run())
    Storage(s.scout_db_path).save_metrics([metric])
    _render([metric], title=f"'{keyword}' 진단")


@app.command()
def expand(
    seed: str,
    depth: int = typer.Option(1, min=1, max=3),
    max_keywords: int = typer.Option(500, "--max"),
):
    """연관 키워드 확장만 (쇼핑 total 미조회, 빠름)."""
    s = get_settings()
    s.require_searchad()

    async def run():
        async with SearchAdClient(
            s.searchad_api_key, s.searchad_secret_key, s.searchad_customer_id, http2=s.scout_http2
        ) as ad:
            return await expand_keywords(ad, [seed], depth=depth, max_keywords=max_keywords)

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


async def _run_mine(
    settings,
    seeds: list[str],
    *,
    depth: int,
    max_keywords: int,
    resume: bool,
    checkpoint_name: str | None,
) -> list[KeywordMetric]:
    ckpt_dir = settings.scout_checkpoint_dir
    ckpt_name = checkpoint_name or Checkpoint.key_for(seeds, {"d": depth, "m": max_keywords}).name
    ckpt_path = ckpt_dir / ckpt_name
    if not resume:
        ckpt_path.unlink(missing_ok=True)

    metrics: list[KeywordMetric] = []
    storage = Storage(settings.scout_db_path)

    async with (
        SearchAdClient(
            settings.searchad_api_key,
            settings.searchad_secret_key,
            settings.searchad_customer_id,
            rps=settings.scout_rps_searchad,
            http2=settings.scout_http2,
        ) as ad,
        ShoppingClient(
            settings.naver_client_id,
            settings.naver_client_secret,
            rps=settings.scout_rps_shopping,
            http2=settings.scout_http2,
        ) as shop,
    ):
        with _progress() as pg:
            expand_task = pg.add_task("[1/2] 연관 키워드 확장", total=depth)

            def _tick(d: int, n: int) -> None:
                pg.update(expand_task, completed=d, description=f"[1/2] 확장 d={d} · {n:,}개")

            related = await expand_keywords(
                ad, seeds, depth=depth, max_keywords=max_keywords, on_progress=_tick,
            )
            pg.update(expand_task, completed=depth)
            console.log(f"확장 완료: {len(related):,} 키워드, 체크포인트 = {ckpt_path.name}")

            with Checkpoint(ckpt_path) as ckpt:
                collect_task = pg.add_task(
                    "[2/2] 쇼핑 상품수 수집",
                    total=len(related),
                    completed=len(ckpt),
                )

                batch: list[KeywordMetric] = []

                def _each(m: KeywordMetric, st: CollectStats) -> None:
                    pg.update(
                        collect_task,
                        completed=st.done + st.skipped,
                        description=f"[2/2] 수집 · 에러 {st.errors} · RPS동적",
                    )

                async for m in attach_product_counts(
                    shop,
                    related,
                    concurrency=settings.scout_concurrency,
                    checkpoint=ckpt,
                    on_each=_each,
                ):
                    metrics.append(m)
                    batch.append(m)
                    if len(batch) >= 200:
                        storage.save_metrics(batch)
                        batch.clear()
                if batch:
                    storage.save_metrics(batch)
    return metrics


@app.command()
def mine(
    seeds_file: Path = typer.Argument(..., exists=True, help="시드 키워드 목록 (한 줄에 하나)"),
    min_vol: int = typer.Option(500, help="최소 월 총검색수"),
    max_comp: float = typer.Option(1.0, help="최대 경쟁강도"),
    max_products: int = typer.Option(0, help="최대 상품수 (0=제한없음)"),
    depth: int = typer.Option(1, min=1, max=3),
    max_keywords: int = typer.Option(2000, "--max"),
    out: Path = typer.Option(Path("gold.xlsx")),
    resume: bool = typer.Option(True, "--resume/--no-resume", help="체크포인트 재개"),
    ckpt: str | None = typer.Option(None, "--ckpt", help="체크포인트 파일명 고정"),
):
    """시드에서 황금키워드 채굴 (중급, 진행바 포함)."""
    s = get_settings()
    s.require_shopping()
    s.require_searchad()
    seeds = [ln.strip() for ln in seeds_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not seeds:
        raise typer.BadParameter("시드 파일이 비어있습니다.")

    metrics = asyncio.run(_run_mine(s, seeds, depth=depth, max_keywords=max_keywords, resume=resume, checkpoint_name=ckpt))
    gold = filter_golden(metrics, min_vol=min_vol, max_comp=max_comp, max_products=max_products or None)
    pd.DataFrame([m.to_row() for m in gold]).to_excel(out, index=False)
    console.print(f"[green]황금키워드 {len(gold):,}개 → {out}[/]")
    _render(gold[:30], title="상위 30개")


@app.command("bulk-mine")
def bulk_mine(
    seeds_file: Path = typer.Argument(..., exists=True),
    out_dir: Path = typer.Option(Path("./out"), "--out-dir"),
    depth: int = typer.Option(2, min=1, max=3),
    max_keywords: int = typer.Option(50_000, "--max", help="대량 상한"),
    min_vol: int = typer.Option(300),
    max_comp: float = typer.Option(1.5),
    chunk: int = typer.Option(1000, help="시드를 이 크기로 분할 처리"),
    resume: bool = typer.Option(True, "--resume/--no-resume"),
):
    """초대량 시드(수천~수만) 분할 처리 + 재개 지원.

    시드를 `chunk` 크기로 쪼개 각 배치마다 독립 체크포인트를 둡니다.
    중단 후 재실행하면 미완료 배치만 이어서 진행.
    """
    s = get_settings()
    s.require_shopping()
    s.require_searchad()
    out_dir.mkdir(parents=True, exist_ok=True)

    seeds = [ln.strip() for ln in seeds_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not seeds:
        raise typer.BadParameter("시드 파일이 비어있습니다.")
    batches = [seeds[i : i + chunk] for i in range(0, len(seeds), chunk)]
    console.print(f"[bold]총 {len(seeds):,} 시드 → {len(batches)} 배치[/]")

    all_metrics: list[KeywordMetric] = []
    for idx, batch in enumerate(batches, start=1):
        console.rule(f"배치 {idx}/{len(batches)} · {len(batch)} 시드")
        ckpt_name = f"bulk_{idx:04d}.jsonl"
        metrics = asyncio.run(
            _run_mine(
                s,
                batch,
                depth=depth,
                max_keywords=max_keywords,
                resume=resume,
                checkpoint_name=ckpt_name,
            )
        )
        all_metrics.extend(metrics)
        # 배치별 중간 엑셀 저장
        gold = filter_golden(metrics, min_vol=min_vol, max_comp=max_comp)
        pd.DataFrame([m.to_row() for m in gold]).to_excel(
            out_dir / f"gold_batch_{idx:04d}.xlsx", index=False
        )
        console.log(f"배치 {idx} 황금 {len(gold):,}개 저장")

    # 전체 통합
    pd.DataFrame([m.to_row() for m in all_metrics]).to_excel(
        out_dir / "all_metrics.xlsx", index=False
    )
    gold_all = filter_golden(all_metrics, min_vol=min_vol, max_comp=max_comp)
    pd.DataFrame([m.to_row() for m in gold_all]).to_excel(
        out_dir / "gold_all.xlsx", index=False
    )
    console.print(
        f"[bold green]완료[/] · 수집 {len(all_metrics):,}개 · 황금 {len(gold_all):,}개 → {out_dir}"
    )
    _render(gold_all[:50], title="전체 Top 50")


@app.command()
def track(
    product_id: str,
    keyword: str = typer.Option(..., "--keyword", "-k"),
    max_pages: int = typer.Option(10, min=1, max=10),
):
    """특정 productId 의 키워드 노출 순위 추적."""
    s = get_settings()
    s.require_shopping()

    async def run() -> int | None:
        async with ShoppingClient(s.naver_client_id, s.naver_client_secret, http2=s.scout_http2) as shop:
            return await shop.find_rank(keyword, product_id, max_pages=max_pages)

    rank = asyncio.run(run())
    Storage(s.scout_db_path).save_rank(product_id, keyword, rank)
    if rank is None:
        console.print(f"[yellow]'{keyword}' 상위 {max_pages*100}위 내 미노출[/]")
    else:
        console.print(f"[green]'{keyword}' → {rank}위[/]")


@app.command()
def trend(
    keyword: str,
    category: str = typer.Option("디지털가전", help="카테고리명 또는 숫자 코드"),
    days: int = typer.Option(90, min=7, max=365),
    period: str = typer.Option("week", help="date|week|month"),
):
    """데이터랩 쇼핑인사이트 키워드 트렌드."""
    s = get_settings()
    s.require_shopping()
    code = resolve(category)

    async def run():
        async with DataLabClient(s.naver_client_id, s.naver_client_secret, http2=s.scout_http2) as d:
            return await d.category_keywords_trend(
                category=code,
                keywords=[(keyword, [keyword])],
                start=date.today() - timedelta(days=days),
                end=date.today(),
                time_unit=period,
            )

    results = asyncio.run(run())
    for res in results:
        table = Table(title=f"{res.title} ({category}) 트렌드")
        table.add_column("기간")
        table.add_column("비율", justify="right")
        for p in res.data:
            table.add_row(p.period, f"{p.ratio:.2f}")
        console.print(table)


@app.command()
def categories():
    """지원하는 카테고리 목록."""
    table = Table(title="네이버 쇼핑 카테고리")
    table.add_column("이름")
    table.add_column("코드")
    for name, code in CATEGORIES.items():
        table.add_row(name, code)
    console.print(table)


@app.command("top")
def top_from_db(
    min_vol: int = typer.Option(500),
    max_comp: float = typer.Option(1.0),
    limit: int = typer.Option(50),
):
    """DB에 쌓인 스냅샷에서 황금키워드 TOP 조회."""
    s = get_settings()
    rows = Storage(s.scout_db_path).query_golden(min_vol=min_vol, max_comp=max_comp, limit=limit)
    table = Table(title=f"저장된 황금키워드 TOP {len(rows)}")
    for col in ["키워드", "상품수", "총검색", "경쟁강도", "점수", "등급", "수집시각"]:
        table.add_column(col)
    for r in rows:
        total_qc = r["monthly_pc"] + r["monthly_mobile"]
        comp = r["competition"]
        table.add_row(
            r["keyword"],
            f"{r['total_products']:,}",
            f"{total_qc:,}",
            f"{comp:.3f}" if comp is not None else "∞",
            f"{r['golden_score']:,.1f}",
            r["grade"],
            r["captured_at"],
        )
    console.print(table)


if __name__ == "__main__":
    app()
