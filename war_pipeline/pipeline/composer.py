"""FFmpeg 합성 — PNG 시퀀스 + 다중 음성 + 자막을 최종 MP4 로.

단계:
    1. 각 라인의 mp3 를 start_time 에 배치한 "믹스 오디오" 생성 (concat + adelay)
    2. PNG 시퀀스를 video 로 인코딩 (-r fps)
    3. 오디오 + 비디오 머지, SRT 를 softsub(mov_text) 로 내장
"""
from __future__ import annotations

import logging
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import FFmpegConfig, RenderFormat
from .scenario import Scenario
from .tts import TTSResult

log = logging.getLogger(__name__)


@dataclass
class ComposeResult:
    video_path: Path


class FFmpegComposer:
    def __init__(self, cfg: FFmpegConfig):
        self.cfg = cfg

    # ---------- helpers ----------

    def _run(self, args: list[str]) -> None:
        log.info("ffmpeg: %s", " ".join(shlex.quote(a) for a in args))
        res = subprocess.run(args, capture_output=True, text=True)
        if res.returncode != 0:
            log.error("ffmpeg stderr:\n%s", res.stderr)
            raise RuntimeError(f"ffmpeg failed ({res.returncode})")

    # ---------- audio mixing ----------

    def build_mixed_audio(
        self,
        scenario: Scenario,
        tts_results: list[TTSResult],
        out_path: Path,
        *,
        total_duration: float,
    ) -> Path:
        """라인별 mp3 를 start_time 에 딜레이 후 믹스."""
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if not tts_results:
            # 무음 생성
            self._run(
                [
                    self.cfg.bin,
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    f"anullsrc=channel_layout=stereo:sample_rate=48000",
                    "-t",
                    f"{total_duration:.3f}",
                    "-c:a",
                    "aac",
                    str(out_path),
                ]
            )
            return out_path

        # -i 입력 N개
        inputs: list[str] = []
        for r in tts_results:
            inputs.extend(["-i", str(r.audio_path)])

        # 필터 그래프:
        #   [0:a]adelay=..|..,apad=whole_dur=T[a0]
        #   [1:a]adelay=..|..,apad=whole_dur=T[a1]
        #   ...
        #   [a0][a1]...amix=inputs=N:normalize=0:dropout_transition=0[aout]
        filter_parts: list[str] = []
        labels: list[str] = []
        for i, r in enumerate(tts_results):
            start_ms = int((scenario.lines[r.line_index].start_time or 0) * 1000)
            label = f"a{i}"
            labels.append(f"[{label}]")
            filter_parts.append(
                f"[{i}:a]adelay={start_ms}|{start_ms},"
                f"apad=whole_dur={total_duration:.3f}[{label}]"
            )
        filter_parts.append(
            f"{''.join(labels)}amix=inputs={len(tts_results)}"
            f":normalize=0:dropout_transition=0[aout]"
        )
        filter_complex = ";".join(filter_parts)

        self._run(
            [
                self.cfg.bin,
                "-y",
                *inputs,
                "-filter_complex",
                filter_complex,
                "-map",
                "[aout]",
                "-t",
                f"{total_duration:.3f}",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(out_path),
            ]
        )
        return out_path

    # ---------- final compose ----------

    def compose(
        self,
        png_dir: Path,
        audio_path: Path,
        srt_path: Path | None,
        out_path: Path,
        fmt: RenderFormat,
        *,
        png_pattern: str = "frame.%04d.png",
    ) -> ComposeResult:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        args = [
            self.cfg.bin,
            "-y",
            "-framerate",
            str(fmt.fps),
            "-i",
            str(png_dir / png_pattern),
            "-i",
            str(audio_path),
        ]
        if srt_path is not None:
            args += ["-i", str(srt_path)]

        args += [
            "-map",
            "0:v",
            "-map",
            "1:a",
        ]
        if srt_path is not None:
            args += ["-map", "2:s", "-c:s", "mov_text"]

        args += [
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(fmt.fps),
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
        self._run(args)
        return ComposeResult(video_path=out_path)
