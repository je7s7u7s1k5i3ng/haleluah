"""offload_to_gdrive 테스트 — 가짜 F:·G: 폴더로 이동·검증·위치표·찾기·되돌리기 확인"""

import json
import os
import time

from storage_offload import offload_to_gdrive as off

MB = 1 << 20


def make(path, size, days_old=30):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(os.urandom(size))
    t = time.time() - days_old * 86400
    os.utime(path, (t, t))


def setup(tmp_path):
    src, gdrive = tmp_path / "F" / "채널 별 롱폼 숏폼", tmp_path / "G" / "내 드라이브"
    make(src / "경제" / "20261001_롱폼" / "원본클립.mp4", 25 * MB)
    make(src / "경제" / "20261001_롱폼" / "대본.md", 1000)
    make(src / "맛가득" / "사진.png", 30 * MB)
    make(src / "맛가득" / "어제찍음.mp4", 25 * MB, days_old=1)
    make(src / "역사" / "작업폴더" / "편집중.mov", 40 * MB)
    (src / "역사" / "작업폴더" / "작업중.lock").write_text("")
    gdrive.mkdir(parents=True)
    return src, gdrive / "보관_원본" / "채널 별 롱폼 숏폼"


def test_preview_moves_nothing(tmp_path):
    src, dst = setup(tmp_path)
    r = off.run(src, dst, log=lambda m: None)
    assert r["상태"] == "미리보기" and r["대상"] == 2
    assert r["건너뜀"]["최근 수정"] == 1 and r["건너뜀"]["작업중 표시 폴더"] >= 1
    assert (src / "맛가득" / "사진.png").exists() and not dst.exists()


def test_execute_moves_verifies_and_leaves_index(tmp_path):
    src, dst = setup(tmp_path)
    r = off.run(src, dst, execute=True, log=lambda m: None)
    assert r["상태"] == "완료" and r["옮김"] == 2 and r["확보GB"] > 0
    assert not (src / "맛가득" / "사진.png").exists()
    assert (dst / "맛가득" / "사진.png").exists()
    assert (src / "경제" / "20261001_롱폼" / "대본.md").exists()        # 문서는 남김
    assert (src / "맛가득" / "어제찍음.mp4").exists()                  # 최근 파일은 남김
    assert (src / "역사" / "작업폴더" / "편집중.mov").exists()          # 작업중 폴더는 남김
    index = json.loads((src / off.INDEX_NAME).read_text(encoding="utf-8"))
    rec = index["파일"]["경제/20261001_롱폼/원본클립.mp4"]
    assert rec["G드라이브"].endswith("원본클립.mp4") and len(rec["sha256"]) == 64
    note = (src / "맛가득" / off.FOLDER_NOTE).read_text(encoding="utf-8")
    assert "G드라이브" in note and "사진.png" in note
    assert not list(dst.rglob("*.part"))


def test_find_and_restore(tmp_path):
    src, dst = setup(tmp_path)
    off.run(src, dst, execute=True, log=lambda m: None)
    hits = off.find(src, "원본클립")
    assert len(hits) == 1
    out = off.restore(src, "경제/20261001_롱폼/원본클립.mp4")
    assert out and os.path.getsize(out) == 25 * MB


def test_verify_mismatch_keeps_original(tmp_path, monkeypatch):
    src, dst = setup(tmp_path)
    real = off.sha256
    calls = {"n": 0}

    def flaky(path, chunk=8 << 20):
        calls["n"] += 1
        return "bad" if str(path).endswith(".part") else real(path, chunk)

    monkeypatch.setattr(off, "sha256", flaky)
    r = off.run(src, dst, execute=True, log=lambda m: None)
    assert r["옮김"] == 0 and len(r["실패"]) == 2
    assert (src / "맛가득" / "사진.png").exists()
    assert not list(dst.rglob("*.part"))


def test_missing_gdrive_is_hold(tmp_path):
    src, dst = setup(tmp_path)
    r = off.run(src, tmp_path / "없는드라이브" / "a" / "b", execute=True, log=lambda m: None)
    assert r["상태"] == "HOLD" and (src / "맛가득" / "사진.png").exists()


def test_final_uploads_stay_unless_asked(tmp_path):
    src, dst = setup(tmp_path)
    make(src / "경제" / "20261001_롱폼" / "최종_업로드본.mp4", 30 * MB)
    r = off.run(src, dst, execute=True, log=lambda m: None)
    assert (src / "경제" / "20261001_롱폼" / "최종_업로드본.mp4").exists()
    assert r["옮김"] == 2
    r2 = off.run(src, dst, execute=True, move_finals=True, log=lambda m: None)
    assert r2["옮김"] == 1 and not (src / "경제" / "20261001_롱폼" / "최종_업로드본.mp4").exists()


def test_program_referenced_files_are_protected(tmp_path):
    src, dst = setup(tmp_path)
    code = tmp_path / "J" / "프로그램 관리"
    code.mkdir(parents=True)
    (code / "config.json").write_text(
        json.dumps({"참고": str(src / "맛가득" / "사진.png").replace("/", "\\")}, ensure_ascii=False), encoding="utf-8")
    (code / "메모.md").write_text(f"{src.name}\\경제\\20261001_롱폼 여기 설명", encoding="utf-8")   # 설명문은 무시
    r = off.run(src, dst, execute=True, code_dirs=[code], log=lambda m: None)
    assert (src / "맛가득" / "사진.png").exists()                       # 프로그램이 쓰는 파일은 남김
    assert not (src / "경제" / "20261001_롱폼" / "원본클립.mp4").exists()   # .md 언급은 보호 안 함
    assert r["옮김"] == 1


def test_size_cap_per_run_and_root_readme(tmp_path):
    src, dst = setup(tmp_path)
    r = off.run(src, dst, execute=True, max_gb=0.03, log=lambda m: None)   # 약 30MB 한도
    assert r["옮김"] == 1
    readme = (src / off.ROOT_README).read_text(encoding="utf-8")
    assert str(dst) in readme and off.INDEX_NAME in readme


def test_cache_drive_low_space_stops_run_and_keeps_originals(tmp_path, monkeypatch):
    src, dst = setup(tmp_path)
    cache = tmp_path / "C"
    cache.mkdir()
    real = off.shutil.disk_usage

    def fake(path):
        u = real(path)
        if str(path) == str(cache):
            return type(u)(u.total, u.used, 27 * MB)   # C: 여유 27MB
        return u

    monkeypatch.setattr(off.shutil, "disk_usage", fake)
    r = off.run(src, dst, execute=True, cache_drive=cache, cache_reserve_gb=0, log=lambda m: None)
    assert r["상태"] == "캐시대기" and r["캐시여유로멈춤"] is True
    assert r["옮김"] == 1                                              # 25MB(경제)는 여유 안, 다음 30MB(맛가득)에서 멈춤
    assert (src / "맛가득" / "사진.png").exists()                       # 못 옮긴 파일은 F에 그대로
    index = json.loads((src / off.INDEX_NAME).read_text(encoding="utf-8"))
    assert index["마지막실행"]["캐시여유로멈춤"] is True


def test_missing_cache_drive_skips_check(tmp_path):
    src, dst = setup(tmp_path)
    r = off.run(src, dst, execute=True, cache_drive=tmp_path / "없는C", log=lambda m: None)
    assert r["상태"] == "완료" and r["옮김"] == 2


def test_preview_writes_full_list_file(tmp_path):
    src, dst = setup(tmp_path)
    lf = tmp_path / "목록" / "이동예정.txt"
    r = off.run(src, dst, list_file=lf, log=lambda m: None)
    text = lf.read_text(encoding="utf-8")
    assert r["상태"] == "미리보기" and "원본클립.mp4" in text and "사진.png" in text and "합계 2개" in text
    assert not dst.exists()
