"""체크포인트 저장소: 중단 후 재개 가능한 대량 수집 지원."""
from __future__ import annotations

import hashlib
from pathlib import Path

import orjson


class Checkpoint:
    """JSON Lines 기반 체크포인트. 처리된 키워드 집합을 기억."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._done: set[str] = set()
        if self.path.exists():
            with self.path.open("rb") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = orjson.loads(line)
                        self._done.add(rec["k"])
                    except Exception:
                        continue
        self._fh = self.path.open("ab")

    @staticmethod
    def key_for(seeds: list[str], params: dict) -> Path:
        h = hashlib.sha1(
            orjson.dumps({"seeds": sorted(seeds), "p": params})
        ).hexdigest()[:12]
        return Path(f"ckpt_{h}.jsonl")

    def done(self, keyword: str) -> bool:
        return keyword in self._done

    def mark(self, keyword: str, metric: dict | None = None) -> None:
        self._done.add(keyword)
        rec = {"k": keyword}
        if metric:
            rec["m"] = metric
        self._fh.write(orjson.dumps(rec) + b"\n")
        self._fh.flush()

    def clear(self) -> None:
        self._fh.close()
        self.path.unlink(missing_ok=True)
        self._done.clear()
        self._fh = self.path.open("ab")

    def close(self) -> None:
        self._fh.close()

    def __len__(self) -> int:
        return len(self._done)

    def __enter__(self) -> "Checkpoint":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
