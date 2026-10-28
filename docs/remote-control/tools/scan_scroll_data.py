# -*- coding: utf-8 -*-
"""스크롤 데이터 폴더 건강검진 (읽기 전용).

사용: python scan_scroll_data.py "K:\\스크롤 데이터" > scan_report.json
- 파일을 수정·삭제·이동하지 않는다.
- 결과 JSON만 설계도 담당자에게 전달하면 된다 (파일 원문은 포함하지 않음).
"""
import collections
import hashlib
import json
import os
import re
import sys
from datetime import datetime

TEMP_PAT = re.compile(r"(\.tmp|\.part|\.crdownload|~\$|\.lock)$", re.I)
DATE_PAT = re.compile(r"(20\d{2})[-_.]?(\d{2})[-_.]?(\d{2})")


def sha1_head(path, limit=1 << 20):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        h.update(f.read(limit))
    return h.hexdigest()


def check_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return "ok", len(data)
        return "ok", 1
    except Exception as e:
        return f"broken:{type(e).__name__}", 0


def check_jsonl(path):
    good = bad = 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                json.loads(line)
                good += 1
            except Exception:
                bad += 1
    return ("ok" if bad == 0 else f"broken_lines:{bad}"), good


def main(root):
    report = {
        "root": root,
        "scanned_at": datetime.now().isoformat(timespec="seconds"),
        "files": 0,
        "bytes": 0,
        "by_ext": collections.Counter(),
        "by_day": collections.Counter(),
        "empty_files": [],
        "temp_leftovers": [],
        "broken": [],
        "name_patterns": collections.Counter(),
        "dup_groups": [],
        "largest": [],
        "newest_mtime": None,
        "oldest_mtime": None,
        "records": 0,
    }
    heads = collections.defaultdict(list)
    sizes = []
    for dirpath, _, names in os.walk(root):
        for name in names:
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root)
            try:
                st = os.stat(path)
            except OSError as e:
                report["broken"].append([rel, f"stat:{e.__class__.__name__}"])
                continue
            report["files"] += 1
            report["bytes"] += st.st_size
            ext = os.path.splitext(name)[1].lower() or "(none)"
            report["by_ext"][ext] += 1
            mt = datetime.fromtimestamp(st.st_mtime)
            report["by_day"][mt.strftime("%Y-%m-%d")] += 1
            iso = mt.isoformat(timespec="seconds")
            report["newest_mtime"] = max(report["newest_mtime"] or iso, iso)
            report["oldest_mtime"] = min(report["oldest_mtime"] or iso, iso)
            # 이름 패턴: 숫자를 # 로 치환해 규칙성 확인
            report["name_patterns"][re.sub(r"\d", "#", name)] += 1
            if st.st_size == 0:
                report["empty_files"].append(rel)
            if TEMP_PAT.search(name):
                report["temp_leftovers"].append(rel)
            sizes.append((st.st_size, rel))
            if ext == ".json":
                status, n = check_json(path)
            elif ext == ".jsonl":
                status, n = check_jsonl(path)
            else:
                status, n = "skip", 0
            report["records"] += n
            if status not in ("ok", "skip"):
                report["broken"].append([rel, status])
            if 0 < st.st_size <= 50 << 20:
                heads[(st.st_size, sha1_head(path))].append(rel)
    report["dup_groups"] = [v for v in heads.values() if len(v) > 1][:50]
    report["largest"] = [[s, r] for s, r in sorted(sizes, reverse=True)[:10]]
    report["by_ext"] = dict(report["by_ext"].most_common())
    report["by_day"] = dict(sorted(report["by_day"].items())[-30:])
    report["name_patterns"] = dict(report["name_patterns"].most_common(20))
    for key in ("empty_files", "temp_leftovers", "broken"):
        report[key + "_count"] = len(report[key])
        report[key] = report[key][:50]
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else r"K:\스크롤 데이터")
