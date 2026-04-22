import asyncio
import logging
import tempfile
from pathlib import Path

import edge_tts

logger = logging.getLogger(__name__)


class TTSEngine:
    def __init__(self, config: dict):
        tts_cfg = config["tts"]
        self.voice = tts_cfg.get("voice", "ko-KR-SunHiNeural")
        self.rate = tts_cfg.get("rate", "+10%")
        self.volume = tts_cfg.get("volume", "+0%")

    async def synthesize(self, text: str, output_path: Path) -> Path:
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
            volume=self.volume,
        )
        await communicate.save(str(output_path))
        logger.info("TTS saved: %s", output_path)
        return output_path

    async def synthesize_with_timestamps(
        self, text: str, output_dir: Path
    ) -> tuple[Path, list[dict]]:
        audio_path = output_dir / "voice.mp3"
        subtitles = []

        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
            volume=self.volume,
        )

        with open(audio_path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    subtitles.append(
                        {
                            "text": chunk["text"],
                            "offset": chunk["offset"] / 10_000_000,
                            "duration": chunk["duration"] / 10_000_000,
                        }
                    )

        logger.info("TTS with timestamps saved: %s (%d words)", audio_path, len(subtitles))
        return audio_path, subtitles
