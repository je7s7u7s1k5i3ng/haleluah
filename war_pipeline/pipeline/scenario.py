"""시나리오 JSON 스키마 (Pydantic)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


Vec3 = tuple[float, float, float]


class Transform(BaseModel):
    location: Vec3 = (0.0, 0.0, 0.0)
    rotation: Vec3 = (0.0, 0.0, 0.0)  # pitch, yaw, roll
    scale: Vec3 = (1.0, 1.0, 1.0)


class CharacterSpawn(BaseModel):
    """레벨에 배치될 캐릭터 정의."""

    id: str = Field(..., description="씬 내 고유 ID")
    # 역할: 저격수/특수부대원/지휘관/병사
    role: Literal["sniper", "spec_ops", "commander", "soldier"]
    # Mixamo FBX -> Unreal 임포트된 블루프린트 경로
    # e.g. "/Game/Characters/BP_Sniper_Female_01"
    blueprint: str
    transform: Transform = Transform()
    # Mixamo 애니메이션 시퀀스 경로 (idle 상태용)
    idle_anim: str | None = None


class CameraKeyframe(BaseModel):
    """시네마틱 카메라 키프레임."""

    time: float = Field(..., ge=0.0, description="씬 시작 기준 초")
    transform: Transform
    fov: float = 90.0
    # 이 순간 포커스 대상 (캐릭터 ID)
    focus_target: str | None = None


class EffectCue(BaseModel):
    """Niagara 이펙트 트리거."""

    time: float = Field(..., ge=0.0)
    # "explosion" | "smoke" | "muzzle_flash" | "dust" | ...
    kind: str
    # Niagara 시스템 에셋 경로
    system: str
    location: Vec3
    rotation: Vec3 = (0.0, 0.0, 0.0)
    scale: float = 1.0
    # 지속 시간 (초)
    duration: float = 2.0


class CharacterCue(BaseModel):
    """캐릭터 애니메이션/이동 큐."""

    time: float = Field(..., ge=0.0)
    character_id: str
    anim: str | None = None  # 애니메이션 시퀀스 경로
    # 선택: 이 순간으로 이동
    move_to: Transform | None = None
    duration: float = 2.0


class ScenarioLine(BaseModel):
    """대사 한 줄 — TTS 음원 + 자막 + 타이밍."""

    speaker: str = "narrator"
    text: str
    # 자동 계산되지만 고정하고 싶으면 명시 가능 (초)
    start_time: float | None = None
    end_time: float | None = None


class Scenario(BaseModel):
    """전체 시나리오."""

    title: str
    # Unreal 레벨 경로 e.g. "/Game/Maps/Battlefield_Desert"
    level: str
    format: Literal["shorts", "longform"] = "shorts"

    characters: list[CharacterSpawn] = []
    cameras: list[CameraKeyframe] = []
    effects: list[EffectCue] = []
    character_cues: list[CharacterCue] = []
    lines: list[ScenarioLine] = []

    # 대사 사이 기본 공백 (초)
    line_gap: float = 0.4
    # 장면 끝에 추가할 여유 시간 (초) — 엔딩 롱테이크 용
    tail_padding: float = 1.0

    @classmethod
    def load(cls, path: str | Path) -> "Scenario":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(data)

    def total_duration(self) -> float:
        """대사가 이미 배치된 상태(start_time/end_time) 기준 총 길이."""
        if not self.lines:
            return self.tail_padding
        end = max((ln.end_time or 0.0) for ln in self.lines)
        return end + self.tail_padding
