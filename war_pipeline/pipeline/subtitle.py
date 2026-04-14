"""자막(SRT) 생성 — 시나리오 대사 기반.

외부 의존성 없이 SRT 포맷을 직접 작성한다.
SRT 규격: https://www.matroska.org/technical/subtitles.html#srt-subtitles
"""
from __future__ import annotations

from pathlib import Path

from .scenario import Scenario


def _format_timestamp(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    ms_total = int(round(seconds * 1000))
    hours, ms_total = divmod(ms_total, 3_600_000)
    minutes, ms_total = divmod(ms_total, 60_000)
    secs, millis = divmod(ms_total, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def build_srt(scenario: Scenario, out_path: Path) -> Path:
    """ScenarioLine 의 start/end 시간을 이용해 SRT 작성."""
    chunks: list[str] = []
    for i, line in enumerate(scenario.lines, start=1):
        if line.start_time is None or line.end_time is None:
            raise ValueError(
                f"line {i} 의 타임스탬프가 아직 계산되지 않았습니다. "
                f"TTS 를 먼저 실행하세요."
            )
        start = _format_timestamp(line.start_time)
        end = _format_timestamp(line.end_time)
        text = (
            f"{line.speaker}: {line.text}"
            if line.speaker and line.speaker != "narrator"
            else line.text
        )
        chunks.append(f"{i}\n{start} --> {end}\n{text}\n")

    out_path.write_text("\n".join(chunks), encoding="utf-8")
    return out_path
