"""Unreal Engine Remote Control API 클라이언트.

Unreal 측 요구사항:
    - Plugins > Remote Control API 활성화
    - Project Settings > Plugins > Web Remote Control:
        * Remote Control HTTP Server Port = 30010
        * Remote Control WebSocket Server Port = 30020
    - Project Settings > Python > "Enable Remote Execution" 체크
    - cmd: `WebControl.StartServer` 로 수동 기동 하거나 프로젝트 StartupScript 에서 자동 시작

이 모듈은 두 가지 방식으로 Unreal 과 통신한다:

1. REST: `/remote/object/call`, `/remote/object/property` (프로퍼티/함수 단위 호출)
2. PythonExec: `/remote/search/assets` 보완 + `/remote/object/call` 로
   `/Script/PythonScriptPlugin.Default__PythonScriptLibrary.ExecutePythonCommand`
   를 호출해서 임의의 Python 스크립트를 실행.

씬 세팅처럼 복잡한 작업은 Unreal 쪽 Python (war_pipeline/unreal_python/*.py) 에
정의된 함수들을 호출하는 식이 가장 안정적이다.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

from .config import UnrealRCConfig

log = logging.getLogger(__name__)


class UnrealRCError(RuntimeError):
    pass


@dataclass
class RCCallResult:
    ok: bool
    status: int
    data: Any


class UnrealRemoteControl:
    """Unreal Remote Control REST 래퍼."""

    def __init__(self, cfg: UnrealRCConfig, timeout: float = 30.0):
        self.cfg = cfg
        self.timeout = timeout
        self._session = requests.Session()

    # ---------- 연결 체크 ----------

    def ping(self) -> bool:
        """Remote Control 서버가 떠 있는지 확인. 살아있으면 True."""
        try:
            r = self._session.get(f"{self.cfg.http_base}/remote/info", timeout=5.0)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def info(self) -> dict:
        r = self._session.get(
            f"{self.cfg.http_base}/remote/info", timeout=self.timeout
        )
        r.raise_for_status()
        return r.json()

    # ---------- 저수준 호출 ----------

    def call(
        self,
        object_path: str,
        function_name: str,
        parameters: dict | None = None,
        *,
        generate_transaction: bool = True,
    ) -> RCCallResult:
        """`ObjectPath.FunctionName(Parameters)` 형태의 RPC 호출."""
        url = f"{self.cfg.http_base}/remote/object/call"
        body = {
            "objectPath": object_path,
            "functionName": function_name,
            "parameters": parameters or {},
            "generateTransaction": generate_transaction,
        }
        log.debug("RC call %s :: %s args=%s", object_path, function_name, parameters)
        r = self._session.put(url, json=body, timeout=self.timeout)
        data: Any
        try:
            data = r.json()
        except ValueError:
            data = r.text
        if r.status_code >= 400:
            raise UnrealRCError(
                f"RC call failed {r.status_code}: {object_path}.{function_name} -> {data}"
            )
        return RCCallResult(ok=True, status=r.status_code, data=data)

    def set_property(
        self, object_path: str, property_name: str, value: Any
    ) -> RCCallResult:
        url = f"{self.cfg.http_base}/remote/object/property"
        body = {
            "objectPath": object_path,
            "propertyName": property_name,
            "propertyValue": {property_name: value},
            "generateTransaction": True,
        }
        r = self._session.put(url, json=body, timeout=self.timeout)
        if r.status_code >= 400:
            raise UnrealRCError(
                f"set_property failed {r.status_code}: {object_path}.{property_name}"
            )
        return RCCallResult(ok=True, status=r.status_code, data=r.json() if r.text else None)

    def get_property(self, object_path: str, property_name: str) -> Any:
        url = (
            f"{self.cfg.http_base}/remote/object/property"
            f"?objectPath={object_path}&propertyName={property_name}"
        )
        r = self._session.get(url, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # ---------- Python 실행 ----------

    def exec_python(self, script: str, *, raise_on_error: bool = True) -> RCCallResult:
        """임의의 Python 스크립트를 Unreal 에서 실행.

        Unreal 내장 PythonScriptLibrary.ExecutePythonCommand 를 사용한다.
        """
        result = self.call(
            "/Script/PythonScriptPlugin.Default__PythonScriptLibrary",
            "ExecutePythonCommand",
            {
                "PythonCommand": script,
            },
        )
        # RC 는 스크립트 예외를 HTTP 500 이 아니라 data 에 실어주는 경우가 있음.
        payload = result.data or {}
        if isinstance(payload, dict):
            err = payload.get("CommandResult") or payload.get("LogOutput")
            if raise_on_error and err and "Error" in str(err):
                raise UnrealRCError(f"Python exec error: {err}")
        return result

    def exec_python_file(self, path: str) -> RCCallResult:
        """Unreal 쪽에 이미 존재하는 .py 파일 실행."""
        script = f"exec(open(r'{path}').read())"
        return self.exec_python(script)

    # ---------- 편의 메서드 ----------

    def load_level(self, level_path: str) -> RCCallResult:
        """에디터에서 레벨 열기."""
        return self.exec_python(
            "import unreal;"
            f"unreal.EditorLevelLibrary.load_level(r'{level_path}')"
        )

    def save_level(self) -> RCCallResult:
        return self.exec_python(
            "import unreal; unreal.EditorLevelLibrary.save_current_level()"
        )

    def spawn_actor(
        self,
        blueprint_path: str,
        location: tuple[float, float, float],
        rotation: tuple[float, float, float] = (0, 0, 0),
        label: str | None = None,
    ) -> RCCallResult:
        lbl = f"'{label}'" if label else "None"
        script = (
            "import unreal\n"
            f"cls = unreal.EditorAssetLibrary.load_blueprint_class(r'{blueprint_path}')\n"
            f"loc = unreal.Vector({location[0]}, {location[1]}, {location[2]})\n"
            f"rot = unreal.Rotator({rotation[0]}, {rotation[1]}, {rotation[2]})\n"
            "actor = unreal.EditorLevelLibrary.spawn_actor_from_class(cls, loc, rot)\n"
            f"label = {lbl}\n"
            "if actor is not None and label: actor.set_actor_label(label)\n"
        )
        return self.exec_python(script)

    def wait_for_server(self, max_wait_s: float = 60.0, interval: float = 1.0) -> bool:
        deadline = time.time() + max_wait_s
        while time.time() < deadline:
            if self.ping():
                return True
            time.sleep(interval)
        return False
