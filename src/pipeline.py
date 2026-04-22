import asyncio
import json
import logging
import shutil
import time
from datetime import datetime
from pathlib import Path

from .script_generator import ScriptGenerator, Script
from .tts_engine import TTSEngine
from .video_composer import VideoComposer
from .uploader import YouTubeUploader

logger = logging.getLogger(__name__)


class ShortsItem:
    def __init__(self, script: Script, work_dir: Path):
        self.script = script
        self.work_dir = work_dir
        self.audio_path: Path | None = None
        self.video_path: Path | None = None
        self.word_timestamps: list[dict] = []
        self.video_id: str | None = None

    @property
    def status_line(self) -> str:
        status = "uploaded" if self.video_id else ("rendered" if self.video_path else "pending")
        return f"[{status}] {self.script.category}/{self.script.title}"


class Pipeline:
    def __init__(self, config: dict):
        self.config = config
        self.script_gen = ScriptGenerator(config)
        self.tts = TTSEngine(config)
        self.composer = VideoComposer(config)
        self.uploader = YouTubeUploader(config)
        self.output_dir = Path(config["batch"]["output_dir"])
        self.parallel_workers = config["batch"].get("parallel_workers", 4)

    async def _process_single(self, script: Script, index: int) -> ShortsItem:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        work_dir = self.output_dir / f"{timestamp}_{index:04d}_{script.category}"
        work_dir.mkdir(parents=True, exist_ok=True)

        item = ShortsItem(script, work_dir)

        meta_path = work_dir / "meta.json"
        meta_path.write_text(
            json.dumps(
                {
                    "title": script.title,
                    "script": script.script,
                    "tags": script.tags,
                    "description": script.description,
                    "category": script.category,
                    "topic": script.topic,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

        logger.info("[%04d] TTS 생성 중: %s", index, script.title)
        audio_path, timestamps = await self.tts.synthesize_with_timestamps(
            script.script, work_dir
        )
        item.audio_path = audio_path
        item.word_timestamps = timestamps

        logger.info("[%04d] 영상 합성 중: %s", index, script.title)
        video_path = work_dir / "shorts.mp4"

        bgm_dir = Path("assets/music")
        bgm_files = list(bgm_dir.glob("*.mp3")) if bgm_dir.exists() else []
        bgm_path = bgm_files[0] if bgm_files else None

        await self.composer.compose(
            audio_path=audio_path,
            word_timestamps=timestamps,
            output_path=video_path,
            bgm_path=bgm_path,
        )
        item.video_path = video_path

        logger.info("[%04d] 완료: %s", index, script.title)
        return item

    async def produce(self, skip_upload: bool = False) -> list[ShortsItem]:
        categories = self.config["content"]["categories"]
        all_scripts: list[Script] = []

        logger.info("=== 대본 생성 시작 ===")
        for cat in categories:
            name = cat["name"]
            template = cat["prompt_template"]
            count = cat["daily_count"]
            logger.info("카테고리 [%s]: %d개 생성 중...", name, count)
            scripts = await self.script_gen.generate_batch(template, count)
            all_scripts.extend(scripts)
            logger.info("카테고리 [%s]: %d개 생성 완료", name, len(scripts))

        logger.info("=== 총 %d개 대본 생성 완료 ===", len(all_scripts))

        logger.info("=== 영상 생산 시작 (workers=%d) ===", self.parallel_workers)
        semaphore = asyncio.Semaphore(self.parallel_workers)
        items: list[ShortsItem] = []

        async def _worker(script: Script, idx: int):
            async with semaphore:
                try:
                    return await self._process_single(script, idx)
                except Exception as e:
                    logger.error("[%04d] 실패: %s - %s", idx, script.title, e)
                    return None

        tasks = [_worker(s, i) for i, s in enumerate(all_scripts)]
        results = await asyncio.gather(*tasks)
        items = [r for r in results if r is not None]

        logger.info("=== %d/%d 영상 생산 완료 ===", len(items), len(all_scripts))

        if not skip_upload:
            logger.info("=== YouTube 업로드 시작 ===")
            for item in items:
                try:
                    vid = self.uploader.upload(
                        video_path=item.video_path,
                        title=item.script.title,
                        description=item.script.description,
                        tags=item.script.tags,
                    )
                    item.video_id = vid
                except Exception as e:
                    logger.error("업로드 실패: %s - %s", item.script.title, e)
            uploaded = sum(1 for i in items if i.video_id)
            logger.info("=== %d/%d 업로드 완료 ===", uploaded, len(items))

        return items

    async def produce_single(
        self, category: str, skip_upload: bool = False
    ) -> ShortsItem | None:
        script = await self.script_gen.generate_one(category)
        item = await self._process_single(script, 0)

        if not skip_upload and item:
            try:
                vid = self.uploader.upload(
                    video_path=item.video_path,
                    title=item.script.title,
                    description=item.script.description,
                    tags=item.script.tags,
                )
                item.video_id = vid
            except Exception as e:
                logger.error("업로드 실패: %s", e)

        return item
