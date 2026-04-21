"""Item Scout CLI."""
from __future__ import annotations

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

import orjson
import pandas as pd
import typer
from rich.console import Console
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


def _emit_json(payload) -> None:
    """Claude Code 등 에이전트가 파싱할 stdout JSON 출력."""
    sys.stdout.buffer.write(orjson.dumps(payload, option=orjson.OPT_INDENT_2))
    sys.stdout.buffer.write(b"\n")


def _metric_dict(m: KeywordMetric) -> dict:
    d = m.to_row()
    if d["competition"] == float("inf"):
        d["competition"] = None
    return d


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
def search(
    keyword: str,
    json_out: bool = typer.Option(False, "--json", help="JSON 출력 (에이전트용)"),
):
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
    storage = Storage(s.scout_db_path)
    storage.save_metrics([metric])
    storage.bump_quota("shopping", 1)
    storage.bump_quota("searchad", 1)
    if json_out:
        _emit_json({"metric": _metric_dict(metric)})
        return
    _render([metric], title=f"'{keyword}' 진단")


@app.command()
def expand(
    seed: str,
    depth: int = typer.Option(1, min=1, max=3),
    max_keywords: int = typer.Option(500, "--max"),
    json_out: bool = typer.Option(False, "--json"),
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
    ranked = sorted(pool.values(), key=lambda r: r.total_qc, reverse=True)
    if json_out:
        _emit_json({
            "seed": seed,
            "count": len(pool),
            "keywords": [
                {
                    "keyword": r.keyword,
                    "monthly_pc": r.monthly_pc_qc,
                    "monthly_mobile": r.monthly_mobile_qc,
                    "total_qc": r.total_qc,
                    "comp_idx": r.comp_idx,
                }
                for r in ranked
            ],
        })
        return
    table = Table(title=f"'{seed}' 연관 키워드 ({len(pool)}개)")
    for col in ["키워드", "PC검색", "모바일", "총검색", "경쟁정도"]:
        table.add_column(col, justify="right" if col != "키워드" else "left")
    for rk in ranked[:100]:
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
    json_out: bool = typer.Option(False, "--json", help="결과 JSON 출력 (엑셀도 저장)"),
    top_n: int = typer.Option(50, "--top", help="JSON/콘솔로 반환할 상위 N개"),
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
    storage = Storage(s.scout_db_path)
    storage.bump_quota("shopping", len(metrics))
    storage.bump_quota("searchad", max(1, len(seeds) // 5 * depth))

    if json_out:
        _emit_json({
            "collected": len(metrics),
            "gold_total": len(gold),
            "out": str(out),
            "top": [_metric_dict(m) for m in gold[:top_n]],
            "grade_counts": {g: sum(1 for m in metrics if m.grade == g) for g in "SABCD"},
        })
        return
    console.print(f"[green]황금키워드 {len(gold):,}개 → {out}[/]")
    _render(gold[:top_n], title=f"상위 {top_n}개")


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
    json_out: bool = typer.Option(False, "--json", help="요약 JSON 출력"),
    top_n: int = typer.Option(50, "--top"),
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
    if json_out:
        _emit_json({
            "batches": len(batches),
            "collected": len(all_metrics),
            "gold_total": len(gold_all),
            "out_dir": str(out_dir),
            "top": [_metric_dict(m) for m in gold_all[:top_n]],
            "grade_counts": {g: sum(1 for m in all_metrics if m.grade == g) for g in "SABCD"},
        })
        return
    console.print(
        f"[bold green]완료[/] · 수집 {len(all_metrics):,}개 · 황금 {len(gold_all):,}개 → {out_dir}"
    )
    _render(gold_all[:top_n], title=f"전체 Top {top_n}")


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
    json_out: bool = typer.Option(False, "--json"),
):
    """DB에 쌓인 스냅샷에서 황금키워드 TOP 조회."""
    s = get_settings()
    rows = Storage(s.scout_db_path).query_golden(min_vol=min_vol, max_comp=max_comp, limit=limit)
    if json_out:
        _emit_json({"count": len(rows), "rows": rows})
        return
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


@app.command()
def query(
    min_vol: int = typer.Option(None, "--min-vol"),
    max_vol: int = typer.Option(None, "--max-vol"),
    max_comp: float = typer.Option(None, "--max-comp"),
    min_comp: float = typer.Option(None, "--min-comp"),
    grade: list[str] = typer.Option([], "--grade", "-g", help="S A B 등 반복 지정"),
    contains: str = typer.Option(None, "--contains", help="키워드 부분 일치"),
    order: str = typer.Option("golden_score", "--order"),
    limit: int = typer.Option(100, "--limit"),
    json_out: bool = typer.Option(True, "--json/--no-json"),
):
    """DB에서 조건별로 키워드 조회 (Claude 기본 조회용, 디폴트 JSON)."""
    s = get_settings()
    rows = Storage(s.scout_db_path).query_keywords(
        min_vol=min_vol,
        max_vol=max_vol,
        min_comp=min_comp,
        max_comp=max_comp,
        grades=list(grade) if grade else None,
        contains=contains,
        order_by=order,
        limit=limit,
    )
    if json_out:
        _emit_json({"count": len(rows), "rows": rows})
        return
    table = Table(title=f"조회 결과 {len(rows)}건")
    for col in ["키워드", "상품수", "총검색", "경쟁강도", "점수", "등급"]:
        table.add_column(col)
    for r in rows:
        comp = r["competition"]
        table.add_row(
            r["keyword"],
            f"{r['total_products']:,}",
            f"{r['total_qc']:,}",
            f"{comp:.3f}" if comp is not None else "∞",
            f"{r['golden_score']:,.1f}",
            r["grade"],
        )
    console.print(table)


@app.command()
def summary(
    json_out: bool = typer.Option(True, "--json/--no-json"),
):
    """DB 요약 + 오늘 API 호출량 (Claude 상태 점검용)."""
    s = get_settings()
    st = Storage(s.scout_db_path)
    data = {
        "db_path": str(s.scout_db_path),
        "summary": st.summary(),
        "quota_today": st.quota_today(),
        "limits": {
            "shopping_daily": 25000,
            "rps_shopping": s.scout_rps_shopping,
            "rps_searchad": s.scout_rps_searchad,
        },
    }
    if json_out:
        _emit_json(data)
        return
    console.print(data)


@app.command()
def estimate(
    seed_count: int = typer.Argument(..., help="시드 키워드 개수"),
    depth: int = typer.Option(2, min=1, max=3),
    max_keywords: int = typer.Option(2000, "--max"),
    json_out: bool = typer.Option(True, "--json/--no-json"),
):
    """bulk-mine 실행 전 호출량·소요시간 예측 (쿨타 초과 사전 차단)."""
    s = get_settings()
    ad_calls = max(1, (seed_count + 4) // 5) * depth
    shop_calls = min(max_keywords, seed_count * 50 * depth)
    est_seconds = max(
        ad_calls / max(s.scout_rps_searchad, 0.1),
        shop_calls / max(s.scout_rps_shopping, 0.1) / max(1, s.scout_concurrency // 4),
    )
    used = Storage(s.scout_db_path).quota_today()
    shop_remaining = 25000 - used.get("shopping", 0)
    warnings = []
    if shop_calls > shop_remaining:
        warnings.append(
            f"쇼핑 API 잔여 {shop_remaining:,} < 예상 {shop_calls:,}. 한도 초과 위험."
        )
    if depth >= 3 and seed_count > 50:
        warnings.append("depth=3 + 시드 많음 → 연관키워드 폭증 가능.")

    payload = {
        "seed_count": seed_count,
        "depth": depth,
        "max_keywords": max_keywords,
        "estimated_calls": {"searchad": ad_calls, "shopping_max": shop_calls},
        "estimated_seconds": round(est_seconds, 1),
        "estimated_minutes": round(est_seconds / 60, 1),
        "quota_today": used,
        "shopping_remaining_today": shop_remaining,
        "warnings": warnings,
    }
    if json_out:
        _emit_json(payload)
        return
    console.print(payload)


@app.command()
def suggest(
    category: str = typer.Option(None, "--category", "-c", help="카테고리명/코드"),
    ttl_hours: int = typer.Option(24, help="이 시간 내 수집된 키워드는 제외"),
    limit: int = typer.Option(10),
    json_out: bool = typer.Option(True, "--json/--no-json"),
):
    """다음 시드 후보 제안. DB 커버리지 분석 기반.

    전략: 아직 미수집이거나 오래된 카테고리 루트 키워드를 반환해서
    Claude가 다음 단계 시드를 고르기 쉽게 함.
    """
    s = get_settings()
    st = Storage(s.scout_db_path)
    base_seeds = list(CATEGORIES.keys()) if not category else [category]
    coverage = st.seed_coverage(base_seeds, ttl_hours=ttl_hours)
    stale = [k for k, fresh in coverage.items() if not fresh]

    # DB에서 가장 높은 경쟁강도 키워드 = 더 긴 꼬리로 쪼갤 필요
    rows = st.query_keywords(min_comp=1.5, order_by="golden_score", limit=limit)
    narrow_candidates = [r["keyword"] for r in rows]

    payload = {
        "stale_categories": stale[:limit],
        "narrow_candidates": narrow_candidates,
        "hint": (
            "stale_categories 는 아직 최근 수집 안 된 카테고리. narrow_candidates 는 "
            "경쟁강도가 높아 롱테일로 쪼개면 황금이 나올 가능성 있는 키워드."
        ),
    }
    if json_out:
        _emit_json(payload)
        return
    console.print(payload)


@app.command()
def seeds_write(
    out: Path = typer.Argument(..., help="생성할 시드 파일 경로"),
    seeds: list[str] = typer.Argument(..., help="공백 구분 시드들"),
):
    """Claude 가 생성한 시드를 파일로 기록 (후속 mine/bulk-mine 입력)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(seeds) + "\n", encoding="utf-8")
    _emit_json({"out": str(out), "count": len(seeds)})


if __name__ == "__main__":
    app()
