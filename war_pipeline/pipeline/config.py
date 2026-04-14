"""전역 설정 (.env + 출력 포맷 프리셋)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv 미설치 시 조용히 무시
    pass


ROOT = Path(__file__).resolve().parent.parent

Format = Literal["shorts", "longform"]


@dataclass(frozen=True)
class RenderFormat:
    name: Format
    width: int
    height: int
    fps: int
    # Movie Render Queue 프리셋 이름 (Unreal 에디터에 동일 이름으로 저장 필요)
    mrq_preset: str


FORMATS: dict[Format, RenderFormat] = {
    "shorts": RenderFormat("shorts", 1080, 1920, 60, "MRQ_Shorts_1080x1920_60"),
    "longform": RenderFormat("longform", 1920, 1080, 60, "MRQ_Longform_1920x1080_60"),
}


@dataclass(frozen=True)
class Paths:
    root: Path
    output: Path
    renders: Path
    audio: Path
    final: Path
    scenarios: Path

    def ensure(self) -> None:
        for p in (self.output, self.renders, self.audio, self.final):
            p.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class ElevenLabsConfig:
    api_key: str
    voice_id: str
    model_id: str


@dataclass(frozen=True)
class UnrealRCConfig:
    host: str
    http_port: int
    ws_port: int

    @property
    def http_base(self) -> str:
        return f"http://{self.host}:{self.http_port}"

    @property
    def ws_url(self) -> str:
        return f"ws://{self.host}:{self.ws_port}"


@dataclass(frozen=True)
class FFmpegConfig:
    bin: str
    probe_bin: str


@dataclass(frozen=True)
class Settings:
    paths: Paths
    elevenlabs: ElevenLabsConfig
    unreal: UnrealRCConfig
    ffmpeg: FFmpegConfig
    default_format: Format


def load_settings() -> Settings:
    paths = Paths(
        root=ROOT,
        output=Path(os.getenv("OUTPUT_DIR", ROOT / "output")),
        renders=Path(os.getenv("RENDER_DIR", ROOT / "output" / "renders")),
        audio=Path(os.getenv("AUDIO_DIR", ROOT / "output" / "audio")),
        final=Path(os.getenv("FINAL_DIR", ROOT / "output" / "final")),
        scenarios=ROOT / "scenarios",
    )
    paths.ensure()

    elevenlabs = ElevenLabsConfig(
        api_key=os.getenv("ELEVENLABS_API_KEY", ""),
        voice_id=os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"),
        model_id=os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"),
    )

    unreal = UnrealRCConfig(
        host=os.getenv("UNREAL_RC_HOST", "127.0.0.1"),
        http_port=int(os.getenv("UNREAL_RC_HTTP_PORT", "30010")),
        ws_port=int(os.getenv("UNREAL_RC_WS_PORT", "30020")),
    )

    ffmpeg = FFmpegConfig(
        bin=os.getenv("FFMPEG_BIN", "ffmpeg"),
        probe_bin=os.getenv("FFPROBE_BIN", "ffprobe"),
    )

    default_format: Format = os.getenv("DEFAULT_FORMAT", "shorts")  # type: ignore[assignment]
    if default_format not in FORMATS:
        default_format = "shorts"

    return Settings(paths, elevenlabs, unreal, ffmpeg, default_format)


def get_format(name: Format | str) -> RenderFormat:
    if name not in FORMATS:
        raise ValueError(f"Unknown format: {name}. Choose from {list(FORMATS)}")
    return FORMATS[name]  # type: ignore[index]
