"""Movie Render Queue 컨트롤러.

Unreal Movie Render Queue(MRQ)를 이용해 PNG 시퀀스를 뽑는다.
MRQ 는 Python API 로 Queue 를 조립-제출할 수 있으므로,
이 모듈은 Remote Control 의 ExecutePythonCommand 로 그걸 촉발한다.

전제조건:
    - Plugins > "Movie Render Queue" 활성화
    - /Game/Cinematics/Preset_* 에 MRQ 프리셋 (해상도/코덱/PNG seq) 저장됨
    - /Game/Cinematics/LS_AutoWar 레벨 시퀀스가 SceneBuilder 에서 생성됨
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from .config import RenderFormat
from .unreal_rc import UnrealRemoteControl

log = logging.getLogger(__name__)


@dataclass
class RenderResult:
    output_dir: Path
    frame_count: int
    fps: int


class MovieRenderQueue:
    def __init__(self, rc: UnrealRemoteControl):
        self.rc = rc

    def render(
        self,
        level: str,
        level_sequence_path: str,
        preset_path: str,
        fmt: RenderFormat,
        output_dir: Path,
        *,
        file_name_format: str = "frame.{frame_number}",
        poll_interval: float = 2.0,
        max_wait_s: float = 60 * 60,  # 1시간 기본
    ) -> RenderResult:
        """MRQ 로 PNG 시퀀스를 렌더하고 프레임 디렉토리를 반환."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Unreal 쪽에 렌더 작업을 제출하고 완료 콜백을 기다린다.
        # 완료 여부는 "sentinel 파일" 로 신호받는다 — MRQ 의 on_finished 콜백이
        # 해당 파일을 생성하도록 Python 스크립트에서 세팅.
        sentinel = output_dir / ".render_done"
        if sentinel.exists():
            sentinel.unlink()

        script = f"""
import unreal, os

out_dir = r'{output_dir.as_posix()}'
sentinel = r'{sentinel.as_posix()}'

subsys = unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem)
queue = subsys.get_queue()
queue.delete_all_jobs()

job = queue.allocate_new_job(unreal.MoviePipelineExecutorJob)
job.sequence = unreal.SoftObjectPath(r'{level_sequence_path}')
job.map = unreal.SoftObjectPath(r'{level}')

preset = unreal.EditorAssetLibrary.load_asset(r'{preset_path}')
if preset is None:
    raise RuntimeError(f"MRQ Preset not found: {preset_path}")
job.set_configuration(preset)

cfg = job.get_configuration()

# 출력 경로/이름 오버라이드
out = cfg.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
out.output_directory = unreal.DirectoryPath(out_dir)
out.file_name_format = r'{file_name_format}'
out.output_resolution = unreal.IntPoint({fmt.width}, {fmt.height})
out.output_frame_rate = unreal.FrameRate({fmt.fps}, 1)

# PNG 출력 설정 보장
cfg.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)

executor = unreal.MoviePipelinePIEExecutor()

def _on_finished(exec_obj, success):
    with open(sentinel, 'w') as f:
        f.write('ok' if success else 'fail')
    unreal.log(f'MRQ finished success={{success}}')

executor.on_executor_finished_delegate.add_callable_unique(_on_finished)
subsys.render_queue_with_executor_instance(executor)
""".strip()

        log.info("Movie Render Queue 실행 중 (PNG 시퀀스 -> %s)", output_dir)
        self.rc.exec_python(script)

        # sentinel 파일 대기
        deadline = time.time() + max_wait_s
        while time.time() < deadline:
            if sentinel.exists():
                status = sentinel.read_text().strip()
                if status == "ok":
                    break
                raise RuntimeError(f"MRQ 렌더 실패: {status}")
            time.sleep(poll_interval)
        else:
            raise TimeoutError(
                f"MRQ 렌더가 {max_wait_s}초 내에 끝나지 않았습니다."
            )

        frames = sorted(output_dir.glob("frame.*.png"))
        if not frames:
            raise RuntimeError(
                f"렌더 완료됐지만 PNG 파일을 찾을 수 없습니다: {output_dir}"
            )
        log.info("렌더 완료: %d 프레임", len(frames))
        return RenderResult(output_dir=output_dir, frame_count=len(frames), fps=fmt.fps)
