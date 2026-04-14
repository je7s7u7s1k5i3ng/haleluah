"""전체 파이프라인 오케스트레이션.

단계:
    1. 시나리오 로드 + 검증
    2. ElevenLabs TTS → mp3 + 타임스탬프
    3. SRT 자막 생성
    4. Unreal Remote Control 연결 확인
    5. SceneBuilder 로 씬/레벨시퀀스/카메라/이펙트 세팅
    6. Movie Render Queue 로 PNG 시퀀스 렌더
    7. FFmpeg 로 오디오 믹싱 + 비디오 합성 + 자막 내장
    8. 최종 MP4 경로 반환
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from .composer import FFmpegComposer
from .config import Settings, get_format
from .render import MovieRenderQueue
from .scenario import Scenario
from .scene_builder import SceneBuilder
from .subtitle import build_srt
from .tts import ElevenLabsTTS
from .unreal_rc import UnrealRemoteControl

log = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    scenario_title: str
    final_video: Path
    audio_mix: Path
    srt_path: Path
    render_dir: Path


class Pipeline:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.rc = UnrealRemoteControl(settings.unreal)
        self.tts = ElevenLabsTTS(settings.elevenlabs, ffmpeg_bin=settings.ffmpeg.bin)
        self.scene_builder = SceneBuilder(self.rc)
        self.mrq = MovieRenderQueue(self.rc)
        self.composer = FFmpegComposer(settings.ffmpeg)

    def run(
        self,
        scenario_path: str | Path,
        *,
        format_name: str | None = None,
        skip_tts: bool = False,
        skip_unreal: bool = False,
        skip_render: bool = False,
    ) -> PipelineResult:
        scenario = Scenario.load(scenario_path)
        fmt = get_format(format_name or scenario.format or self.settings.default_format)
        log.info(
            "=== Pipeline start :: %s (%s %dx%d@%dfps) ===",
            scenario.title,
            fmt.name,
            fmt.width,
            fmt.height,
            fmt.fps,
        )

        paths = self.settings.paths
        job_slug = self._slug(scenario.title)
        job_audio_dir = paths.audio / job_slug
        job_render_dir = paths.renders / job_slug
        job_final = paths.final / f"{job_slug}.mp4"
        job_mix = job_audio_dir / "mix.m4a"
        job_srt = job_audio_dir / "subs.srt"
        job_audio_dir.mkdir(parents=True, exist_ok=True)
        job_render_dir.mkdir(parents=True, exist_ok=True)

        # --- 1) TTS ---
        if skip_tts:
            log.info("[skip] TTS")
            tts_results = []
        else:
            tts_results = self.tts.synthesize_scenario(
                scenario, self.settings, audio_dir=job_audio_dir
            )

        # --- 2) 자막 ---
        if scenario.lines:
            build_srt(scenario, job_srt)
            log.info("SRT 저장: %s", job_srt)

        # --- 3) Unreal 씬 세팅 ---
        if skip_unreal:
            log.info("[skip] Unreal scene build")
            scene_result = None
        else:
            if not self.rc.ping():
                raise RuntimeError(
                    f"Unreal Remote Control 서버({self.rc.cfg.http_base})에 "
                    "연결할 수 없습니다. 에디터에서 플러그인을 켜고 "
                    "WebControl.StartServer 로 서버를 기동하세요."
                )
            scene_result = self.scene_builder.build(scenario, fmt)

        # --- 4) 렌더 ---
        if skip_render or scene_result is None:
            log.info("[skip] Movie Render Queue")
            render_result = None
        else:
            render_result = self.mrq.render(
                level=scenario.level,
                level_sequence_path=scene_result.level_sequence_path,
                preset_path=scene_result.preset_path,
                fmt=fmt,
                output_dir=job_render_dir,
            )

        # --- 5) 오디오 믹싱 ---
        total_dur = scenario.total_duration()
        self.composer.build_mixed_audio(
            scenario, tts_results, job_mix, total_duration=total_dur
        )

        # --- 6) 최종 합성 ---
        srt_arg = job_srt if scenario.lines else None
        if render_result is None:
            log.warning(
                "렌더 산출물이 없어 최종 합성은 스킵합니다. "
                "오디오/자막 미리보기는 %s 에 저장되어 있습니다.",
                job_audio_dir,
            )
            return PipelineResult(
                scenario_title=scenario.title,
                final_video=job_final,  # 아직 생성 안 됨
                audio_mix=job_mix,
                srt_path=job_srt,
                render_dir=job_render_dir,
            )

        self.composer.compose(
            png_dir=render_result.output_dir,
            audio_path=job_mix,
            srt_path=srt_arg,
            out_path=job_final,
            fmt=fmt,
        )
        log.info("=== 최종 MP4: %s ===", job_final)

        return PipelineResult(
            scenario_title=scenario.title,
            final_video=job_final,
            audio_mix=job_mix,
            srt_path=job_srt,
            render_dir=job_render_dir,
        )

    @staticmethod
    def _slug(s: str) -> str:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in s.strip())
        return safe[:64] or "scene"
