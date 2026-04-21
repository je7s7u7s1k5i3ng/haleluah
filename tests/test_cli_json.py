"""CLI 의 JSON 출력 smoke 테스트 (네트워크 없이 가능한 서브커맨드만)."""
import json
import subprocess
import sys
from pathlib import Path


def _run(args, cwd):
    env = {"PATH": subprocess.os.environ["PATH"]}
    # 파이썬 모듈로 직접 호출 (scout 엔트리포인트 설치 의존 회피)
    return subprocess.run(
        [sys.executable, "-m", "item_scout", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env={**subprocess.os.environ, "SCOUT_DB_PATH": str(Path(cwd) / "test.db")},
    )


def test_summary_json(tmp_path):
    res = _run(["summary", "--json"], tmp_path)
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert "summary" in data
    assert "quota_today" in data
    assert "limits" in data


def test_estimate_json(tmp_path):
    res = _run(["estimate", "100", "--depth", "2", "--max", "1000", "--json"], tmp_path)
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["seed_count"] == 100
    assert data["estimated_calls"]["searchad"] >= 20
    assert "warnings" in data


def test_estimate_warns_when_exceeding_quota(tmp_path):
    # shopping 잔여를 일부러 소진시킴
    db = Path(tmp_path) / "test.db"
    import item_scout.storage.db as storage_mod
    storage_mod.Storage(db).bump_quota("shopping", 24999)

    res = _run(["estimate", "500", "--depth", "3", "--max", "5000", "--json"], tmp_path)
    data = json.loads(res.stdout)
    assert any("쇼핑 API" in w for w in data["warnings"])


def test_query_json_empty(tmp_path):
    res = _run(["query", "--limit", "5", "--json"], tmp_path)
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data == {"count": 0, "rows": []}


def test_seeds_write(tmp_path):
    out = tmp_path / "seeds.txt"
    res = _run(["seeds-write", str(out), "캠핑", "차박", "오토캠핑"], tmp_path)
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["count"] == 3
    assert out.read_text(encoding="utf-8").splitlines() == ["캠핑", "차박", "오토캠핑"]
