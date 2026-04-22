#!/usr/bin/env python3
"""
haleluah - YouTube Shorts 자동 대량 생산 시스템
하루 100개 쇼츠를 자동으로 생성, 렌더링, 업로드합니다.
"""
import asyncio
import logging
import sys
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from src.pipeline import Pipeline

console = Console()


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


def load_config(config_path: str = "config/settings.yaml") -> dict:
    path = Path(config_path)
    if not path.exists():
        console.print(f"[red]설정 파일을 찾을 수 없습니다: {path}[/red]")
        sys.exit(1)
    with open(path) as f:
        return yaml.safe_load(f)


@click.group()
@click.option("--config", default="config/settings.yaml", help="설정 파일 경로")
@click.option("--verbose", "-v", is_flag=True, help="상세 로그 출력")
@click.pass_context
def cli(ctx, config, verbose):
    """haleluah - YouTube Shorts 자동 대량 생산 시스템"""
    setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config(config)


@cli.command()
@click.option("--skip-upload", is_flag=True, help="영상만 생성하고 업로드 건너뛰기")
@click.pass_context
def produce(ctx, skip_upload):
    """전체 배치 생산 실행 (설정 파일의 daily_target만큼 생산)"""
    config = ctx.obj["config"]
    pipeline = Pipeline(config)

    console.print("\n[bold green]===  haleluah 쇼츠 대량 생산 시작 ===[/bold green]\n")

    target = config["batch"]["daily_target"]
    console.print(f"  목표: [bold]{target}[/bold]개")
    console.print(f"  병렬 워커: [bold]{config['batch']['parallel_workers']}[/bold]개")
    console.print(f"  업로드: [bold]{'건너뛰기' if skip_upload else '활성화'}[/bold]")
    console.print()

    items = asyncio.run(pipeline.produce(skip_upload=skip_upload))

    table = Table(title="생산 결과")
    table.add_column("번호", style="dim")
    table.add_column("카테고리", style="cyan")
    table.add_column("제목", style="white")
    table.add_column("상태", style="green")

    for i, item in enumerate(items, 1):
        status = "업로드 완료" if item.video_id else "생성 완료"
        table.add_row(str(i), item.script.category, item.script.title, status)

    console.print(table)
    console.print(f"\n[bold green]총 {len(items)}개 쇼츠 생산 완료![/bold green]\n")


@cli.command()
@click.argument("category", type=click.Choice(["motivation", "fun_facts", "life_tips", "history"]))
@click.option("--skip-upload", is_flag=True, help="업로드 건너뛰기")
@click.pass_context
def single(ctx, category, skip_upload):
    """단일 쇼츠 생성 (테스트용)"""
    config = ctx.obj["config"]
    pipeline = Pipeline(config)

    console.print(f"\n[cyan]카테고리 [{category}] 단일 쇼츠 생성 중...[/cyan]\n")

    item = asyncio.run(pipeline.produce_single(category, skip_upload=skip_upload))

    if item:
        console.print(f"  제목: [bold]{item.script.title}[/bold]")
        console.print(f"  대본: {item.script.script[:100]}...")
        console.print(f"  영상: {item.video_path}")
        if item.video_id:
            console.print(f"  URL: https://youtube.com/shorts/{item.video_id}")
        console.print("\n[green]완료![/green]")
    else:
        console.print("[red]생성 실패[/red]")


@cli.command()
@click.option("--count", "-n", default=5, help="생성할 대본 수")
@click.argument("category", type=click.Choice(["motivation", "fun_facts", "life_tips", "history"]))
@click.pass_context
def scripts(ctx, count, category):
    """대본만 생성 (영상 제작 없이)"""
    config = ctx.obj["config"]
    from src.script_generator import ScriptGenerator

    gen = ScriptGenerator(config)
    console.print(f"\n[cyan]{category} 대본 {count}개 생성 중...[/cyan]\n")

    results = asyncio.run(gen.generate_batch(category, count))

    for i, s in enumerate(results, 1):
        console.print(f"[bold]--- {i}. {s.title} ---[/bold]")
        console.print(s.script)
        console.print(f"[dim]태그: {', '.join(s.tags)}[/dim]\n")

    console.print(f"[green]{len(results)}개 대본 생성 완료[/green]")


@cli.command()
@click.pass_context
def status(ctx):
    """현재 설정 및 상태 확인"""
    config = ctx.obj["config"]

    table = Table(title="시스템 설정")
    table.add_column("항목", style="cyan")
    table.add_column("값", style="white")

    table.add_row("LLM 모델", config["llm"]["model"])
    table.add_row("TTS 엔진", config["tts"]["engine"])
    table.add_row("TTS 음성", config["tts"]["voice"])
    table.add_row("영상 해상도", f"{config['video']['width']}x{config['video']['height']}")
    table.add_row("일일 목표", str(config["batch"]["daily_target"]))
    table.add_row("병렬 워커", str(config["batch"]["parallel_workers"]))
    table.add_row("업로드 상태", config["youtube"]["privacy_status"])

    console.print(table)

    cat_table = Table(title="콘텐츠 카테고리")
    cat_table.add_column("카테고리", style="cyan")
    cat_table.add_column("템플릿", style="white")
    cat_table.add_column("일일 수량", style="green")

    for cat in config["content"]["categories"]:
        cat_table.add_row(cat["name"], cat["prompt_template"], str(cat["daily_count"]))

    console.print(cat_table)

    import shutil
    ffmpeg = shutil.which("ffmpeg")
    console.print(f"\nFFmpeg: {'[green]설치됨[/green]' if ffmpeg else '[red]미설치[/red]'}")

    yt_token = Path("config/token.json").exists()
    yt_secret = Path("config/client_secret.json").exists()
    console.print(f"YouTube API: {'[green]인증됨[/green]' if yt_token else '[yellow]미인증[/yellow]'}")
    console.print(f"클라이언트 시크릿: {'[green]있음[/green]' if yt_secret else '[red]없음[/red]'}")


if __name__ == "__main__":
    cli()
