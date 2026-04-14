"""Unreal 없이 TTS + 자막 + 오디오 믹스만 돌려 미리보기.

유튜브 쇼츠 AB 테스트용 — 음성 먼저 만들어 길이 감 잡고 카메라 타이밍 설계에 사용.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import load_settings  # noqa: E402
from pipeline.orchestrator import Pipeline  # noqa: E402


def main(scenario: str) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    p = Pipeline(settings)
    r = p.run(scenario, skip_unreal=True, skip_render=True)
    print(f"audio mix: {r.audio_mix}")
    print(f"subs    : {r.srt_path}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: tts_preview.py <scenario.json>")
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
