"""
영상 대본(자막) 수집 — yt-dlp가 설치돼 있을 때만 동작

- 공개 자막·자동 생성 한국어 자막만 내려받는다(영상 파일은 받지 않음).
- 분석용 로컬 보관만 한다. 대본·영상을 다시 올리거나 재배포하지 않는다.
- 연속 실패 3회면 그 회차는 대본 수집을 멈추고 HOLD로 기록한다(막힘을 우회하지 않음).
"""

import re
import shutil
import subprocess
import time

_TS = re.compile(r"(\d+):(\d{2}):(\d{2})[.,](\d{3})\s+-->")


def available():
    return shutil.which("yt-dlp") is not None


def parse_vtt(text):
    """VTT → [(시작초, 문장)], 자동 자막의 반복 줄은 합친다."""
    cues, start, last = [], None, None
    for line in text.splitlines():
        line = line.strip()
        m = _TS.match(line)
        if m:
            h, mi, s, ms = map(int, m.groups())
            start = h * 3600 + mi * 60 + s + ms / 1000
            continue
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) or start is None:
            continue
        clean = re.sub(r"<[^>]+>", "", line).strip()
        if clean and clean != last:
            cues.append((round(start, 2), clean))
            last = clean
    return cues


class TranscriptCollector:
    def __init__(self, out_dir, settings, log=print):
        self.out_dir = out_dir
        self.settings = settings
        self.log = log
        self.fail_streak = 0
        self.stopped = False

    def fetch(self, video_id):
        if self.stopped or not available():
            return None
        target = self.out_dir / video_id
        cmd = [
            "yt-dlp", "--skip-download", "--write-subs", "--write-auto-subs",
            "--sub-langs", "ko.*,ko", "--sub-format", "vtt", "--no-warnings",
            "-o", str(target), f"https://www.youtube.com/watch?v={video_id}",
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=90, check=False)
        except subprocess.TimeoutExpired:
            pass
        files = sorted(self.out_dir.glob(f"{video_id}*.vtt"))
        time.sleep(self.settings.get("request_sleep_sec", 1.0) * 2)
        if not files:
            self.fail_streak += 1
            if self.fail_streak >= 3:
                self.stopped = True
                self.log("[대본] 연속 3회 실패 — 이번 회차 대본 수집 중단(HOLD)")
            return None
        self.fail_streak = 0
        return parse_vtt(files[0].read_text(encoding="utf-8", errors="replace"))
