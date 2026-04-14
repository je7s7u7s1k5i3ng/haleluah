"""시나리오를 Unreal 씬으로 번역.

전략:
    - 복잡한 구성(레벨 시퀀스 생성, 카메라 트랙, 캐릭터 애니메이션 바인딩)은
      Remote Control 의 단일 REST 호출로 표현하기가 번거롭기 때문에,
      Unreal 프로젝트 /Content/Python/war_setup.py 에 정의된 함수를
      Remote Control 의 ExecutePythonCommand 로 호출한다.
    - 이 모듈은 그 인자들을 JSON 직렬화해서 넘기는 얇은 어댑터 역할.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import RenderFormat
from .scenario import Scenario
from .unreal_rc import UnrealRemoteControl

log = logging.getLogger(__name__)


@dataclass
class SceneBuildResult:
    level_sequence_path: str
    preset_path: str
    duration: float


class SceneBuilder:
    def __init__(self, rc: UnrealRemoteControl):
        self.rc = rc

    def build(
        self,
        scenario: Scenario,
        fmt: RenderFormat,
        *,
        level_sequence_path: str = "/Game/Cinematics/LS_AutoWar",
        preset_path: str = "/Game/Cinematics/Preset_AutoWar",
    ) -> SceneBuildResult:
        """Unreal 쪽 war_setup.build_scene(config) 을 호출."""
        config = {
            "title": scenario.title,
            "level": scenario.level,
            "format": {
                "name": fmt.name,
                "width": fmt.width,
                "height": fmt.height,
                "fps": fmt.fps,
                "mrq_preset": fmt.mrq_preset,
            },
            "level_sequence_path": level_sequence_path,
            "preset_path": preset_path,
            "characters": [c.model_dump() for c in scenario.characters],
            "cameras": [c.model_dump() for c in scenario.cameras],
            "effects": [e.model_dump() for e in scenario.effects],
            "character_cues": [c.model_dump() for c in scenario.character_cues],
            "lines": [
                {
                    "speaker": ln.speaker,
                    "text": ln.text,
                    "start_time": ln.start_time,
                    "end_time": ln.end_time,
                }
                for ln in scenario.lines
            ],
            "duration": scenario.total_duration(),
        }

        payload = json.dumps(config, ensure_ascii=False)
        # Unreal 쪽 스크립트 로드 + 함수 호출
        script = (
            "import json, importlib, sys\n"
            "import unreal\n"
            "try:\n"
            "    import war_setup\n"
            "    importlib.reload(war_setup)\n"
            "except ImportError as e:\n"
            "    unreal.log_error(f'war_setup import failed: {e}')\n"
            "    raise\n"
            f"_cfg = json.loads(r'''{payload}''')\n"
            "war_setup.build_scene(_cfg)\n"
        )
        log.info("Unreal build_scene 호출 중...")
        self.rc.exec_python(script)
        log.info("Unreal 씬 빌드 완료")

        return SceneBuildResult(
            level_sequence_path=level_sequence_path,
            preset_path=preset_path,
            duration=scenario.total_duration(),
        )
