"""파이프라인 실행 CLI.

예시:
    # 기본 (shorts)
    python scripts/run_pipeline.py scenarios/sample_scenario.json

    # 롱폼
    python scripts/run_pipeline.py scenarios/sample_scenario.json --format longform

    # TTS 만 — Unreal 연결 없이 오디오/자막 미리보기
    python scripts/run_pipeline.py scenarios/sample_scenario.json --skip-unreal --skip-render
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import load_settings  # noqa: E402
from pipeline.orchestrator import Pipeline  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Unreal 전쟁 시나리오 파이프라인")
    p.add_argument("scenario", help="시나리오 JSON 경로")
    p.add_argument(
        "--format",
        choices=["shorts", "longform"],
        default=None,
        help="출력 포맷 (시나리오 기본값 덮어쓰기)",
    )
    p.add_argument("--skip-tts", action="store_true", help="TTS 단계 스킵")
    p.add_argument("--skip-unreal", action="store_true", help="Unreal 씬 빌드 스킵")
    p.add_argument("--skip-render", action="store_true", help="MRQ 렌더 스킵")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = load_settings()
    pipeline = Pipeline(settings)
    result = pipeline.run(
        args.scenario,
        format_name=args.format,
        skip_tts=args.skip_tts,
        skip_unreal=args.skip_unreal,
        skip_render=args.skip_render,
    )
    print("\n=========== DONE ===========")
    print(f"title : {result.scenario_title}")
    print(f"video : {result.final_video}")
    print(f"audio : {result.audio_mix}")
    print(f"srt   : {result.srt_path}")
    print(f"frames: {result.render_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
