import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from .subtitle_renderer import SubtitleRenderer

logger = logging.getLogger(__name__)


class VideoComposer:
    def __init__(self, config: dict):
        self.config = config
        vid_cfg = config["video"]
        self.width = vid_cfg["width"]
        self.height = vid_cfg["height"]
        self.fps = vid_cfg["fps"]
        self.bg_color = vid_cfg.get("background_color", "#000000")
        self.subtitle_renderer = SubtitleRenderer(config)

    def _create_solid_background(self, duration: float, output_path: Path) -> Path:
        r = int(self.bg_color[1:3], 16)
        g = int(self.bg_color[3:5], 16)
        b = int(self.bg_color[5:7], 16)
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=0x{self.bg_color[1:]}:s={self.width}x{self.height}:d={duration}:r={self.fps}",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            str(output_path),
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def _get_background_video(self, duration: float, work_dir: Path) -> Path:
        bg_dir = Path("assets/backgrounds")
        bg_videos = list(bg_dir.glob("*.mp4")) if bg_dir.exists() else []

        bg_path = work_dir / "background.mp4"
        if bg_videos:
            source = bg_videos[0]
            cmd = [
                "ffmpeg", "-y",
                "-stream_loop", "-1",
                "-i", str(source),
                "-t", str(duration),
                "-vf", f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-an",
                str(bg_path),
            ]
            subprocess.run(cmd, capture_output=True, check=True)
        else:
            self._create_solid_background(duration, bg_path)

        return bg_path

    def _get_audio_duration(self, audio_path: Path) -> float:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            str(audio_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())

    def _build_subtitle_filter(self, subtitle_clips: list[dict]) -> str:
        filters = []
        for i, clip in enumerate(subtitle_clips):
            escaped = clip["text"].replace("'", "\\'").replace(":", "\\:")
            filters.append(
                f"drawtext=text='{escaped}'"
                f":fontsize={self.subtitle_renderer.font_size}"
                f":fontcolor={self.subtitle_renderer.font_color}"
                f":borderw={self.subtitle_renderer.stroke_width}"
                f":bordercolor={self.subtitle_renderer.stroke_color}"
                f":x=(w-text_w)/2:y=(h-text_h)/2"
                f":enable='between(t,{clip['start']:.2f},{clip['end']:.2f})'"
            )
        return ",".join(filters) if filters else "null"

    async def compose(
        self,
        audio_path: Path,
        word_timestamps: list[dict],
        output_path: Path,
        bgm_path: Path | None = None,
    ) -> Path:
        work_dir = output_path.parent
        duration = self._get_audio_duration(audio_path)

        loop = asyncio.get_event_loop()

        bg_path = await loop.run_in_executor(
            None, self._get_background_video, duration, work_dir
        )

        subtitle_clips = self.subtitle_renderer.generate_subtitle_clips(
            word_timestamps, work_dir
        )

        filter_str = self._build_subtitle_filter(subtitle_clips)

        cmd = ["ffmpeg", "-y", "-i", str(bg_path), "-i", str(audio_path)]

        if bgm_path and bgm_path.exists():
            cmd.extend(["-i", str(bgm_path)])
            cmd.extend([
                "-filter_complex",
                f"[0:v]{filter_str}[v];[1:a]volume=1.0[voice];[2:a]volume=0.15[bgm];[voice][bgm]amix=inputs=2:duration=first[a]",
                "-map", "[v]", "-map", "[a]",
            ])
        else:
            cmd.extend([
                "-vf", filter_str,
                "-map", "0:v", "-map", "1:a",
            ])

        cmd.extend([
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            str(output_path),
        ])

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error("FFmpeg failed: %s", stderr.decode())
            raise RuntimeError(f"FFmpeg failed: {stderr.decode()[:500]}")

        logger.info("Video composed: %s (%.1fs)", output_path, duration)
        return output_path
