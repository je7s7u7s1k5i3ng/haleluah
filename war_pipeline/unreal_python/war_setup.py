"""Unreal Engine 프로젝트 측 씬 빌더 스크립트.

배치 위치:
    <Your UE Project>/Content/Python/war_setup.py

호출:
    파이프라인의 SceneBuilder 가 Remote Control 의 ExecutePythonCommand 로
    `war_setup.build_scene(cfg: dict)` 를 호출한다.

구성:
    1. 지정된 레벨 열기
    2. 기존 시퀀스 제거 + 새 LevelSequence 생성
    3. 캐릭터 스폰 + 가능한 경우 애니메이션 바인딩
    4. Cine Camera Actor + 카메라 컷 트랙 구성
    5. 이펙트 큐를 Niagara Component 로 스폰
    6. 시퀀스 길이/fps 설정
    7. MRQ Preset 해상도 오버라이드

주의:
    Unreal Python API 는 에디터 모드에서만 동작한다.
    게임(PIE) 빌드에서는 이 스크립트가 의미 없다.
"""
from __future__ import annotations

import json
from typing import Any

try:
    import unreal  # type: ignore
except ImportError:  # Unreal 밖에서 import 시 -- 문법 체크용
    unreal = None  # type: ignore


LS_NAME = "LS_AutoWar"
LS_FOLDER = "/Game/Cinematics"


def _vec(v):
    return unreal.Vector(float(v[0]), float(v[1]), float(v[2]))


def _rot(r):
    # (pitch, yaw, roll)
    return unreal.Rotator(float(r[0]), float(r[1]), float(r[2]))


def _transform(t: dict) -> "unreal.Transform":
    return unreal.Transform(
        location=_vec(t.get("location", [0, 0, 0])),
        rotation=_rot(t.get("rotation", [0, 0, 0])),
        scale=_vec(t.get("scale", [1, 1, 1])),
    )


# ---------- main ----------


def build_scene(cfg: dict[str, Any]) -> None:
    if unreal is None:
        raise RuntimeError("This script must run inside Unreal Editor.")

    unreal.log(f"[war_setup] build_scene: {cfg.get('title')}")
    _load_level(cfg["level"])

    seq = _create_level_sequence(cfg)
    _spawn_characters(cfg.get("characters", []))
    _bind_character_cues(seq, cfg.get("character_cues", []), cfg.get("format", {}).get("fps", 60))
    _build_cameras(seq, cfg.get("cameras", []), cfg.get("format", {}).get("fps", 60))
    _trigger_effects(seq, cfg.get("effects", []), cfg.get("format", {}).get("fps", 60))

    duration = float(cfg.get("duration", 10.0))
    fps = int(cfg.get("format", {}).get("fps", 60))
    _set_sequence_range(seq, duration, fps)

    _ensure_mrq_preset(cfg)
    unreal.EditorAssetLibrary.save_loaded_asset(seq)
    unreal.EditorLevelLibrary.save_current_level()
    unreal.log("[war_setup] build_scene 완료")


# ---------- 세부 단계 ----------


def _load_level(level_path: str) -> None:
    if not unreal.EditorAssetLibrary.does_asset_exist(level_path):
        raise RuntimeError(f"레벨 에셋이 존재하지 않음: {level_path}")
    unreal.EditorLevelLibrary.load_level(level_path)


def _create_level_sequence(cfg: dict) -> "unreal.LevelSequence":
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    folder = cfg.get("level_sequence_path", f"{LS_FOLDER}/{LS_NAME}").rsplit("/", 1)[0]
    name = cfg.get("level_sequence_path", f"{LS_FOLDER}/{LS_NAME}").rsplit("/", 1)[1]

    if not unreal.EditorAssetLibrary.does_directory_exist(folder):
        unreal.EditorAssetLibrary.make_directory(folder)

    full = f"{folder}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(full):
        unreal.EditorAssetLibrary.delete_asset(full)

    seq = asset_tools.create_asset(
        asset_name=name,
        package_path=folder,
        asset_class=unreal.LevelSequence,
        factory=unreal.LevelSequenceFactoryNew(),
    )
    unreal.log(f"[war_setup] LevelSequence 생성: {full}")
    return seq


def _spawn_characters(characters: list[dict]) -> None:
    level = unreal.EditorLevelLibrary
    for c in characters:
        bp = c["blueprint"]
        cls = unreal.EditorAssetLibrary.load_blueprint_class(bp)
        if cls is None:
            unreal.log_warning(f"[war_setup] 블루프린트 로드 실패: {bp}")
            continue
        t = c.get("transform", {})
        loc = _vec(t.get("location", [0, 0, 0]))
        rot = _rot(t.get("rotation", [0, 0, 0]))
        actor = level.spawn_actor_from_class(cls, loc, rot)
        if actor is None:
            unreal.log_warning(f"[war_setup] 스폰 실패: {bp}")
            continue
        actor.set_actor_label(c["id"])
        # idle anim — 가능한 SkeletalMeshComponent 찾아 play
        if c.get("idle_anim"):
            _play_anim_on_actor(actor, c["idle_anim"], looping=True)


def _find_skeletal_mesh(actor) -> "unreal.SkeletalMeshComponent | None":
    comps = actor.get_components_by_class(unreal.SkeletalMeshComponent)
    return comps[0] if comps else None


def _play_anim_on_actor(actor, anim_path: str, *, looping: bool = False) -> None:
    sk = _find_skeletal_mesh(actor)
    if sk is None:
        unreal.log_warning(f"[war_setup] SkeletalMeshComponent 없음: {actor.get_actor_label()}")
        return
    anim = unreal.EditorAssetLibrary.load_asset(anim_path)
    if anim is None:
        unreal.log_warning(f"[war_setup] 애니메이션 로드 실패: {anim_path}")
        return
    sk.play_animation(anim, looping)


def _bind_character_cues(seq, cues: list[dict], fps: int) -> None:
    """시퀀스에 캐릭터별 애니메이션 섹션 추가."""
    level = unreal.EditorLevelLibrary
    all_actors = {a.get_actor_label(): a for a in level.get_all_level_actors()}
    for cue in cues:
        actor = all_actors.get(cue["character_id"])
        if actor is None:
            unreal.log_warning(f"[war_setup] 캐릭터 없음: {cue['character_id']}")
            continue

        binding = seq.add_possessable(actor)
        if cue.get("anim"):
            anim = unreal.EditorAssetLibrary.load_asset(cue["anim"])
            if anim is not None:
                track = binding.add_track(unreal.MovieSceneSkeletalAnimationTrack)
                section = track.add_section()
                section.set_range(
                    int(cue["time"] * fps),
                    int((cue["time"] + cue.get("duration", 2.0)) * fps),
                )
                section.params.animation = anim


def _build_cameras(seq, cameras: list[dict], fps: int) -> None:
    if not cameras:
        return

    # CameraCutTrack 생성
    cut_track = seq.add_master_track(unreal.MovieSceneCameraCutTrack)

    # 첫 카메라만 생성 후 키프레임으로 이동/회전
    first = cameras[0]
    cam_actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.CineCameraActor,
        _vec(first["transform"]["location"]),
        _rot(first["transform"]["rotation"]),
    )
    cam_actor.set_actor_label("AutoWarCam")
    cam_binding = seq.add_possessable(cam_actor)

    transform_track = cam_binding.add_track(unreal.MovieScene3DTransformTrack)
    transform_section = transform_track.add_section()
    transform_section.set_range(0, int(cameras[-1]["time"] * fps) + fps)

    # 각 채널(Loc X,Y,Z / Rot X,Y,Z) 별로 키프레임 추가
    channels = transform_section.get_channels()
    for k in cameras:
        frame = int(k["time"] * fps)
        loc = k["transform"]["location"]
        rot = k["transform"]["rotation"]
        values = [loc[0], loc[1], loc[2], rot[0], rot[1], rot[2]]
        for ch, v in zip(channels[:6], values):
            ch.add_key(unreal.FrameNumber(frame), float(v))

    # CameraCut: 전 구간
    cut_section = cut_track.add_section()
    cut_section.set_range(0, int(cameras[-1]["time"] * fps) + fps)
    cut_section.set_camera_binding_id(seq.make_binding_id(cam_binding))

    # FOV 키프레임
    fov_channels = cam_actor.get_cine_camera_component()
    # FOV 변경은 스크립트 단순화를 위해 마지막 값만 사용
    if cameras[-1].get("fov"):
        cam_actor.get_cine_camera_component().set_editor_property(
            "current_focal_length",
            _fov_to_focal_length(float(cameras[-1]["fov"])),
        )


def _fov_to_focal_length(fov_deg: float, sensor_width_mm: float = 36.0) -> float:
    import math

    rad = math.radians(fov_deg)
    return (sensor_width_mm / 2) / math.tan(rad / 2)


def _trigger_effects(seq, effects: list[dict], fps: int) -> None:
    for eff in effects:
        sys = unreal.EditorAssetLibrary.load_asset(eff["system"])
        if sys is None:
            unreal.log_warning(f"[war_setup] Niagara 시스템 로드 실패: {eff['system']}")
            continue

        loc = _vec(eff["location"])
        rot = _rot(eff.get("rotation", [0, 0, 0]))
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.NiagaraActor, loc, rot
        )
        actor.set_actor_label(f"FX_{eff['kind']}_{int(eff['time']*1000)}")
        actor.set_actor_scale3d(_vec([eff.get("scale", 1.0)] * 3))
        nc = actor.get_niagara_component()
        nc.set_asset(sys)
        nc.set_auto_activate(False)  # 시퀀스에서 activate

        binding = seq.add_possessable(actor)
        track = binding.add_track(unreal.MovieSceneNiagaraEmitterTrack)
        section = track.add_section()
        start = int(eff["time"] * fps)
        end = int((eff["time"] + eff.get("duration", 2.0)) * fps)
        section.set_range(start, end)


def _set_sequence_range(seq, duration: float, fps: int) -> None:
    seq.set_display_rate(unreal.FrameRate(fps, 1))
    end_tick = int(duration * fps)
    seq.set_playback_start(0)
    seq.set_playback_end(end_tick)


def _ensure_mrq_preset(cfg: dict) -> None:
    preset_path = cfg.get("preset_path")
    if not preset_path:
        return
    if unreal.EditorAssetLibrary.does_asset_exist(preset_path):
        return

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    folder, name = preset_path.rsplit("/", 1)
    preset = asset_tools.create_asset(
        asset_name=name,
        package_path=folder,
        asset_class=unreal.MoviePipelinePrimaryConfig,
        factory=None,
    )
    # 기본 세팅 구성
    out = preset.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
    out.output_resolution = unreal.IntPoint(
        int(cfg["format"]["width"]), int(cfg["format"]["height"])
    )
    out.output_frame_rate = unreal.FrameRate(int(cfg["format"]["fps"]), 1)
    preset.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)
    preset.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
    unreal.EditorAssetLibrary.save_loaded_asset(preset)
