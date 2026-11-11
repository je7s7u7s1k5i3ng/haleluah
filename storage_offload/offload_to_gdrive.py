# -*- coding: utf-8 -*-
r"""
F: 원본 파일 → G드라이브 이동 + 위치표 남기기 (용량 확보)

기본값은 '미리보기'(아무것도 안 옮김). --실행 을 붙여야 실제로 옮긴다.

    python offload_to_gdrive.py                       # 미리보기: 무엇을 얼마나 옮길지 표시
    python offload_to_gdrive.py --실행                 # 실제 이동
    python offload_to_gdrive.py --찾기 "파일이름 일부"    # 옮긴 파일이 G드라이브 어디 있는지
    python offload_to_gdrive.py --되돌리기 "상대경로"     # G드라이브에서 원래 자리로 복사

이동 규칙 (안전 순서):
  1) G드라이브 같은 상대 경로에 복사
  2) 크기 + SHA-256 비교 → 같을 때만 원본 삭제 (다르면 원본 유지, 실패 기록)
  3) F: 맨 위에 00_G드라이브_이동위치.json (전체 위치표),
     옮긴 파일이 있던 폴더마다 _G드라이브에_있음.txt (그 폴더 안내) 를 남긴다

옮기지 않는 것 (F:에 그대로 남김):
  - 코드·문서·설정(.py .json .md .txt 등) = 각 폴더에 심어 둔 성공 패턴 기록 → 절대 안 옮김
  - 작은 파일(기본 20MB 미만) — 썸네일 이미지 등 성공 패턴 참고 자료
  - 유튜브에 올린 최종 영상(이름·폴더에 최종/완성/업로드/final 이 들어간 것) — --최종본도이동 을 붙여야만 옮김
  - 프로그램(J:\프로그램 관리, I:\자동화 프로그램)의 코드·설정이 경로로 가리키는 파일·폴더
  - 최근 N일(기본 14일) 안에 고친 파일 — 작업 중일 수 있음
  - 폴더 안에 작업중.lock / 00_작업중 / _보관금지 표시가 있는 폴더
  - 용량 제한은 기본 없음(400GB도 한 번에 대상). 대신 캐시 드라이브 여유가 부족해지면 그 회차를 멈춘다 (아래)

왜 C:가 나오나:
  구글 드라이브 앱은 G:에 넣은 파일을 클라우드에 다 올릴 때까지 '캐시 폴더'(기본 C:\Users\...\AppData\Local\Google\DriveFS)에
  임시로 들고 있는다. 그래서 F→G 이동 중에는 C: 공간이 잠깐 줄어든다. 업로드가 끝나면 다시 비워진다.
  → 매 파일 전에 캐시 드라이브(기본 C:\) 여유를 재고, 여유가 --캐시여유GB(기본 20GB) 아래로 내려갈 것 같으면 그 회차를 멈춘다.
  → 구글 드라이브 설정에서 캐시 위치를 F:로 바꿨다면 --캐시드라이브 F:\ 로 실행한다.
"""

import argparse
import hashlib
import re
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

VERSION = "1.2.0"
DEFAULT_SRC = r"F:\채널 별 롱폼 숏폼"
DEFAULT_DST = r"G:\내 드라이브\보관_원본\채널 별 롱폼 숏폼"
DEFAULT_CODE_DIRS = [r"J:\프로그램 관리", r"I:\자동화 프로그램"]
ROOT_README = "00_원본은_G드라이브에_있음.txt"
INDEX_NAME = "00_G드라이브_이동위치.json"
FOLDER_NOTE = "_G드라이브에_있음.txt"
MEDIA_EXT = {
    ".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm", ".mts", ".m2ts",
    ".wav", ".mp3", ".m4a", ".flac", ".aac",
    ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".psd", ".heic",
    ".zip", ".7z", ".rar",
}
KEEP_MARKERS = {"작업중.lock", "00_작업중", "_보관금지"}
FINAL_WORDS = ("최종", "완성", "업로드", "final", "upload")
# 실제로 프로그램이 읽는 파일만 검사 (.md·.txt 설명문 속 언급은 참조로 보지 않음)
CODE_EXT = {".py", ".json", ".bat", ".cmd", ".ps1", ".yaml", ".yml", ".ini", ".cfg", ".toml"}


def sha256(path, chunk=8 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def load_index(src):
    p = Path(src) / INDEX_NAME
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {
        "_설명": "이 폴더의 원본 파일 중 G드라이브로 옮긴 것의 위치표. 찾을 때는 '상대경로'로 검색하거나 "
                 "python offload_to_gdrive.py --찾기 \"이름\" 을 쓴다.",
        "원본폴더": str(src), "보관폴더": None, "버전": VERSION, "파일": {},
    }


def save_index(src, index):
    p = Path(src) / INDEX_NAME
    tmp = p.with_suffix(".json.part")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)


def write_folder_note(folder, dst_folder, names):
    note = Path(folder) / FOLDER_NOTE
    old = note.read_text(encoding="utf-8").splitlines()[3:] if note.exists() else []
    lines = sorted(set(old) | {f"- {n}" for n in names})
    note.write_text(
        "이 폴더의 원본 일부는 용량 확보를 위해 G드라이브로 옮겼습니다.\n"
        f"위치: {dst_folder}\n"
        f"전체 목록: 맨 위 폴더의 {INDEX_NAME}\n" + "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def is_final(rel):
    low = str(rel).lower()
    return any(w in low for w in FINAL_WORDS)


def referenced_paths(src, code_dirs, max_bytes=2 << 20):
    """프로그램 코드·설정 안에서 원본 폴더 아래 경로를 가리키는 부분을 모은다 (그 경로는 옮기지 않음)."""
    name = Path(src).name
    pat = re.compile(re.escape(name) + r"[\\/]+([^\"'\n\r<>|*?]+)")
    found = set()
    for d in code_dirs or []:
        d = Path(d)
        if not d.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(d):
            dirnames[:] = [x for x in dirnames if x not in (".git", "__pycache__", "node_modules", ".venv", "venv")]
            for fn in filenames:
                p = Path(dirpath) / fn
                if p.suffix.lower() not in CODE_EXT:
                    continue
                try:
                    if p.stat().st_size > max_bytes:
                        continue
                    text = p.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                for m in pat.finditer(text):
                    rel = m.group(1).replace("\\\\", "/").replace("\\", "/").strip().strip("/").rstrip(".,;:)")
                    # 실제로 있는 가장 깊은 경로까지만 보호 (뒤에 붙은 다른 글자는 버림)
                    parts, keep = [x for x in rel.split("/") if x], None
                    for i in range(len(parts), 0, -1):
                        if (Path(src) / Path(*parts[:i])).exists():
                            keep = "/".join(parts[:i])
                            break
                    if keep:
                        found.add(keep)
    return found


def _protected(rel, refs):
    r = str(rel).replace("\\", "/")
    return any(r == x or r.startswith(x + "/") for x in refs)


def write_root_readme(src, dst):
    (Path(src) / ROOT_README).write_text(
        "이 폴더의 큰 원본 파일(촬영 원본·중간 렌더·소스 영상 등)은 용량 확보를 위해 G드라이브로 옮겼습니다.\n"
        "폴더 구조는 그대로 같습니다. 같은 하위 경로를 아래 위치에서 찾으면 됩니다.\n\n"
        f"G드라이브 위치: {dst}\n"
        f"전체 목록(경로·크기·SHA-256·옮긴 시각): {INDEX_NAME}\n"
        f"폴더별 안내: 각 폴더의 {FOLDER_NOTE}\n\n"
        "찾기:     python offload_to_gdrive.py --찾기 \"파일이름 일부\"\n"
        "되돌리기: python offload_to_gdrive.py --되돌리기 \"상대경로\"\n\n"
        "남겨 둔 것: 성공 패턴 기록(.md .json .txt .py 등), 20MB 미만 파일, 최종 업로드본, 프로그램이 참조하는 파일, "
        "최근 14일 안에 고친 파일, 작업중 표시 폴더\n",
        encoding="utf-8",
    )


def plan(src, min_mb, days, now=None, refs=(), move_finals=False, max_gb=0):
    now = now or time.time()
    src = Path(src)
    picks, skipped = [], {"작은 파일·문서": 0, "최종 업로드본": 0, "프로그램이 참조": 0,
                          "최근 수정": 0, "작업중 표시 폴더": 0, "이번 회차 한도 초과": 0}
    budget = max_gb * (1 << 30) if max_gb else None
    for dirpath, dirnames, filenames in os.walk(src):
        if KEEP_MARKERS & set(filenames + dirnames):
            skipped["작업중 표시 폴더"] += len(filenames)
            dirnames[:] = []
            continue
        dirnames.sort()                     # 매번 같은 순서로 (재실행·보고 일관성)
        for name in sorted(filenames):
            if name in (INDEX_NAME, FOLDER_NOTE) or name.endswith(".part"):
                continue
            p = Path(dirpath) / name
            try:
                st = p.stat()
            except OSError:
                continue
            if p.suffix.lower() not in MEDIA_EXT or st.st_size < min_mb * (1 << 20):
                skipped["작은 파일·문서"] += 1
                continue
            rel = p.relative_to(src)
            if not move_finals and is_final(rel):
                skipped["최종 업로드본"] += 1
                continue
            if _protected(rel, refs):
                skipped["프로그램이 참조"] += 1
                continue
            if now - st.st_mtime < days * 86400:
                skipped["최근 수정"] += 1
                continue
            if budget is not None and st.st_size > budget:
                skipped["이번 회차 한도 초과"] += 1
                continue
            if budget is not None:
                budget -= st.st_size
            picks.append((p, st.st_size))
    return picks, skipped


def move_one(p, src, dst):
    rel = p.relative_to(src)
    target = Path(dst) / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    shutil.copy2(p, part)
    src_hash = sha256(p)
    if part.stat().st_size != p.stat().st_size or sha256(part) != src_hash:
        part.unlink(missing_ok=True)
        return None, "검증 불일치(원본 유지)"
    os.replace(part, target)
    p.unlink()
    return {"상대경로": str(rel).replace("\\", "/"), "G드라이브": str(target), "크기": target.stat().st_size,
            "sha256": src_hash, "이동시각": datetime.now().isoformat(timespec="seconds")}, None


DEFAULT_CACHE_DRIVE = "C:\\"


def run(src, dst, min_mb=20, days=14, execute=False, log=print, code_dirs=None,
        move_finals=False, max_gb=0, gdrive_root=None, cache_drive=DEFAULT_CACHE_DRIVE, cache_reserve_gb=20,
        list_file=None):
    src, dst = Path(src), Path(dst)
    if not src.is_dir():
        log(f"[중단] 원본 폴더 없음: {src}")
        return {"상태": "HOLD", "이유": "원본 폴더 없음"}
    refs = referenced_paths(src, code_dirs)
    if refs:
        log(f"프로그램이 가리키는 경로 {len(refs)}개는 옮기지 않음 (예: {sorted(refs)[:3]})")
    picks, skipped = plan(src, min_mb, days, refs=refs, move_finals=move_finals, max_gb=max_gb)
    total = sum(s for _, s in picks)
    log(f"옮길 대상 {len(picks)}개 · {total / (1 << 30):.2f}GB  (건너뜀: {skipped})")
    if list_file:                        # 옮길 대상 전체 목록 (미리보기 검토용)
        lf = Path(list_file)
        lf.parent.mkdir(parents=True, exist_ok=True)
        lf.write_text("\n".join(f"{p.relative_to(src)}\t{s / (1 << 20):.0f}MB" for p, s in picks)
                      + f"\n\n합계 {len(picks)}개 · {total / (1 << 30):.2f}GB\n건너뜀 {skipped}\n", encoding="utf-8")
        log(f"전체 목록 저장: {lf}")
    if not execute:
        for p, s in picks[:30]:
            log(f"  [미리보기] {p.relative_to(src)}  {s / (1 << 20):.0f}MB")
        return {"상태": "미리보기", "대상": len(picks), "용량GB": round(total / (1 << 30), 2), "건너뜀": skipped}
    root = Path(gdrive_root) if gdrive_root else dst.parents[1]   # 기본: G:\내 드라이브
    if not root.is_dir():
        log(f"[중단] G드라이브가 연결되지 않음: {root}")
        return {"상태": "HOLD", "이유": "G드라이브 없음"}
    dst.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(root).free
    if free < total * 1.1:
        log(f"[주의] G드라이브 쪽 여유 {free / (1 << 30):.1f}GB < 필요 {total * 1.1 / (1 << 30):.1f}GB — 가능한 만큼만 옮긴다")
    cache = Path(cache_drive) if cache_drive else None
    if cache is not None and not cache.exists():
        log(f"[주의] 캐시 드라이브 {cache} 를 찾지 못해 캐시 여유 검사를 건너뜀")
        cache = None
    reserve = cache_reserve_gb * (1 << 30)
    if cache is not None:
        log(f"캐시 드라이브 {cache} 여유 {shutil.disk_usage(cache).free / (1 << 30):.1f}GB (최소 {cache_reserve_gb}GB 남김)")
    index = load_index(src)
    index["보관폴더"] = str(dst)
    moved, failed, freed = 0, [], 0
    by_folder = {}
    cache_stop = False
    for p, size in picks:
        if cache is not None and shutil.disk_usage(cache).free - size < reserve:
            log(f"[멈춤] 캐시 드라이브 {cache} 여유가 {cache_reserve_gb}GB 아래로 내려감 — "
                f"구글 드라이브 업로드가 끝난 뒤 다시 실행하세요 (남은 {len(picks) - moved - len(failed)}개는 다음 회차)")
            cache_stop = True
            break
        if shutil.disk_usage(root).free < size * 1.1:
            failed.append([str(p.relative_to(src)), "G드라이브 쪽 공간 부족"])
            continue
        try:
            rec, err = move_one(p, src, dst)
        except OSError as e:
            rec, err = None, f"{type(e).__name__}: {e}"
        if err:
            failed.append([str(p.relative_to(src)), err])
            log(f"  [실패] {p.name}: {err}")
            continue
        index["파일"][rec["상대경로"]] = rec
        by_folder.setdefault(p.parent, []).append(p.name)
        moved += 1
        freed += size
        if moved % 20 == 0:
            save_index(src, index)          # 중간에 끊겨도 위치표가 남도록
    for folder, names in by_folder.items():
        rel_folder = folder.relative_to(src)
        write_folder_note(folder, dst / rel_folder, names)
    index["마지막실행"] = {"시각": datetime.now().isoformat(timespec="seconds"), "옮김": moved,
                       "확보GB": round(freed / (1 << 30), 2), "실패": failed[:50], "캐시여유로멈춤": cache_stop}
    save_index(src, index)
    write_root_readme(src, dst)
    log(f"완료: {moved}개 이동, {freed / (1 << 30):.2f}GB 확보, 실패 {len(failed)}개 → 위치표 {src / INDEX_NAME}")
    state = "일부실패" if failed else ("캐시대기" if cache_stop else "완료")
    return {"상태": state, "옮김": moved, "확보GB": round(freed / (1 << 30), 2), "실패": failed,
            "캐시여유로멈춤": cache_stop}


def find(src, keyword):
    index = load_index(src)
    return [r for k, r in index["파일"].items() if keyword.lower() in k.lower()]


def restore(src, rel):
    index = load_index(src)
    rec = index["파일"].get(rel.replace("\\", "/"))
    if not rec:
        return None
    target = Path(src) / rec["상대경로"]
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(rec["G드라이브"], target)
    if sha256(target) != rec["sha256"]:
        target.unlink(missing_ok=True)
        raise OSError("되돌린 파일의 SHA-256이 위치표와 다름 — G드라이브 사본을 확인하세요")
    return str(target)


def main(argv=None):
    ap = argparse.ArgumentParser(description="F: 원본 → G드라이브 이동 + 위치표")
    ap.add_argument("--원본", default=DEFAULT_SRC)
    ap.add_argument("--보관", default=DEFAULT_DST)
    ap.add_argument("--최소MB", type=int, default=20)
    ap.add_argument("--최근일", type=int, default=14, help="이 일수 안에 고친 파일은 옮기지 않음")
    ap.add_argument("--최대GB", type=int, default=0, help="한 번 실행에 옮길 최대 용량 (기본 0=제한 없음, 캐시 여유 검사가 대신 멈춤)")
    ap.add_argument("--최종본도이동", "--include-finals", dest="최종본도이동", action="store_true", help="유튜브에 올린 최종 영상도 옮김")
    ap.add_argument("--코드폴더", action="append", help="참조 검사할 프로그램 폴더 (여러 번 가능)")
    ap.add_argument("--캐시드라이브", "--cache-drive", dest="캐시드라이브", default=DEFAULT_CACHE_DRIVE,
                    help="구글 드라이브 앱 캐시가 있는 드라이브 (기본 C:\\)")
    ap.add_argument("--캐시여유GB", "--cache-reserve-gb", dest="캐시여유GB", type=int, default=20,
                    help="캐시 드라이브에 최소로 남길 여유 (기본 20GB)")
    ap.add_argument("--목록파일", "--list-file", dest="목록파일", help="옮길 대상 전체 목록을 이 파일에 저장")
    ap.add_argument("--실행", "--execute", dest="실행", action="store_true")
    ap.add_argument("--찾기", "--find", dest="찾기")
    ap.add_argument("--되돌리기", "--restore", dest="되돌리기")
    a = ap.parse_args(argv)
    if a.찾기:
        for r in find(a.원본, a.찾기):
            print(f"{r['상대경로']}  →  {r['G드라이브']}")
        return 0
    if a.되돌리기:
        out = restore(a.원본, a.되돌리기)
        print(f"복원: {out}" if out else "위치표에 없는 경로입니다")
        return 0 if out else 1
    result = run(a.원본, a.보관, a.최소MB, a.최근일, a.실행, code_dirs=a.코드폴더 or DEFAULT_CODE_DIRS,
                 move_finals=a.최종본도이동, max_gb=a.최대GB,
                 cache_drive=a.캐시드라이브, cache_reserve_gb=a.캐시여유GB, list_file=a.목록파일)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["상태"] in ("미리보기", "완료", "캐시대기") else 1


if __name__ == "__main__":
    sys.exit(main())
