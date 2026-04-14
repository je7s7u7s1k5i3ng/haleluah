"""Unreal Remote Control 연결 테스트.

사용법:
    python scripts/test_rc_connection.py

성공 시:
    - /remote/info 응답 출력
    - Unreal Python 한 줄 실행 (unreal.log)
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

# 루트 패키지 import 를 위해 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import load_settings  # noqa: E402
from pipeline.unreal_rc import UnrealRemoteControl  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("rc-test")


def main() -> int:
    settings = load_settings()
    rc = UnrealRemoteControl(settings.unreal)

    log.info("Remote Control 주소: %s", rc.cfg.http_base)

    if not rc.ping():
        log.error(
            "연결 실패. 다음을 확인하세요:\n"
            "  1) Unreal Editor 가 켜져 있는지\n"
            "  2) Edit > Plugins 에서 'Remote Control API' 활성화\n"
            "  3) Edit > Project Settings > Plugins > Remote Control 에서\n"
            "     HTTP Server Port = %d, WebSocket Port = %d\n"
            "  4) 에디터 Cmd 창에서 `WebControl.StartServer` 실행\n"
            "  5) 방화벽이 %d 포트를 막고 있지 않은지",
            rc.cfg.http_port,
            rc.cfg.ws_port,
            rc.cfg.http_port,
        )
        return 1

    info = rc.info()
    log.info("서버 정보:\n%s", json.dumps(info, indent=2, ensure_ascii=False))

    log.info("Python 한 줄 실행 테스트...")
    result = rc.exec_python(
        "import unreal; unreal.log('[RC] ping from war_pipeline test')"
    )
    log.info("Python exec 결과: %s", result.data)

    log.info("성공. Remote Control 연결 정상.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
