"""ElevenLabs TTS — 대사별 음성 파일 생성 + 문자 단위 타임스탬프 추출.

ElevenLabs는 `with-timestamps` 엔드포인트로 문자 단위 alignment 를 제공한다.
이걸 이용해 각 ScenarioLine 의 start_time / end_time 을 자동 계산한다.
"""
from __future__ import annotations

import base64
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

import requests

from .config import ElevenLabsConfig, Settings
from .scenario import Scenario, ScenarioLine

log = logging.getLogger(__name__)


API_BASE = "https://api.elevenlabs.io/v1"


@dataclass
class TTSResult:
    line_index: int
    audio_path: Path
    duration: float  # 초
    # 문자 단위 타임스탬프 (각 문자가 화면상 언제 시작/끝나는지)
    char_starts: list[float]
    char_ends: list[float]
    chars: list[str]


class ElevenLabsTTS:
    def __init__(self, cfg: ElevenLabsConfig, ffmpeg_bin: str = "ffmpeg"):
        if not cfg.api_key:
            raise RuntimeError(
                "ELEVENLABS_API_KEY 가 비어있습니다. .env 에 설정하세요."
            )
        self.cfg = cfg
        self.ffmpeg_bin = ffmpeg_bin
        self._session = requests.Session()
        self._session.headers.update(
            {
                "xi-api-key": cfg.api_key,
                "accept": "application/json",
                "content-type": "application/json",
            }
        )

    # ---------- low-level ----------

    def _synthesize_with_timestamps(
        self,
        text: str,
        *,
        voice_id: str | None = None,
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        style: float = 0.0,
    ) -> tuple[bytes, list[str], list[float], list[float]]:
        """raw mp3 바이트 + 문자 타임스탬프 반환."""
        vid = voice_id or self.cfg.voice_id
        url = f"{API_BASE}/text-to-speech/{vid}/with-timestamps"
        payload = {
            "text": text,
            "model_id": self.cfg.model_id,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
                "style": style,
                "use_speaker_boost": True,
            },
        }
        r = self._session.post(url, json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()

        audio_b64 = data["audio_base64"]
        audio_bytes = base64.b64decode(audio_b64)

        alignment = data.get("alignment") or data.get("normalized_alignment") or {}
        chars: list[str] = alignment.get("characters", list(text))
        starts: list[float] = alignment.get("character_start_times_seconds", [])
        ends: list[float] = alignment.get("character_end_times_seconds", [])

        # fallback — alignment 비어있으면 균등분배
        if not starts or not ends:
            log.warning(
                "ElevenLabs alignment 데이터가 비어있음 — 균등 분배로 fallback"
            )
            approx_len = len(chars) * 0.06  # 대략 문자당 60ms
            step = approx_len / max(len(chars), 1)
            starts = [i * step for i in range(len(chars))]
            ends = [(i + 1) * step for i in range(len(chars))]

        return audio_bytes, chars, starts, ends

    def _mp3_duration(self, mp3_path: Path) -> float:
        """ffprobe 로 mp3 길이 측정."""
        try:
            out = subprocess.check_output(
                [
                    self.ffmpeg_bin.replace("ffmpeg", "ffprobe"),
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(mp3_path),
                ],
                text=True,
            )
            return float(out.strip())
        except Exception:
            log.warning("ffprobe 실패 — 파일 크기 기반 추정")
            size = mp3_path.stat().st_size
            return size / 16_000.0  # 아주 거친 추정 (128kbps)

    # ---------- high-level ----------

    def synthesize_line(
        self, line: ScenarioLine, out_path: Path
    ) -> TTSResult:
        audio_bytes, chars, starts, ends = self._synthesize_with_timestamps(line.text)
        out_path.write_bytes(audio_bytes)
        duration = ends[-1] if ends else self._mp3_duration(out_path)
        return TTSResult(
            line_index=-1,
            audio_path=out_path,
            duration=duration,
            char_starts=starts,
            char_ends=ends,
            chars=chars,
        )

    def synthesize_scenario(
        self,
        scenario: Scenario,
        settings: Settings,
        *,
        audio_dir: Path | None = None,
    ) -> list[TTSResult]:
        """대사 전체를 TTS 하고 start_time/end_time 을 시나리오에 채워 넣는다."""
        results: list[TTSResult] = []
        cursor = 0.0  # 누적 시간
        audio_dir = audio_dir or settings.paths.audio
        audio_dir.mkdir(parents=True, exist_ok=True)

        for i, line in enumerate(scenario.lines):
            out = audio_dir / f"line_{i:03d}.mp3"
            log.info(f"[{i + 1}/{len(scenario.lines)}] TTS: {line.text[:40]}...")
            result = self.synthesize_line(line, out)
            result.line_index = i

            line.start_time = cursor
            line.end_time = cursor + result.duration
            cursor = line.end_time + scenario.line_gap

            results.append(result)

        return results
