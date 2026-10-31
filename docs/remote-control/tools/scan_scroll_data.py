# -*- coding: utf-8 -*-
"""스크롤 데이터 폴더 건강검진 V2 (읽기 전용).

사용: python scan_scroll_data.py "K:\\스크롤 데이터" > scan_report.json
- 파일을 수정·삭제·이동하지 않는다.
- 결과 JSON만 전달하면 된다 (레코드 원문은 포함하지 않음, 필드 이름·비율만).

V2 추가: 레코드 필드 채움률, 레코드 중복 키, 날짜 공백, 크기 이상치, txt/csv 줄 수.
"""
import collections
import hashlib
import json
import os
import re
import statistics
import sys
from datetime import date, datetime, timedelta

VERSION = "V2"
TEMP_PAT = re.compile(r"(\.tmp|\.part|\.crdownload|~\$|\.lock)$", re.I)
KEY_CANDIDATES = ("id", "url", "link", "href", "key", "uid", "post_id", "video_id")
MAX_RECORDS_PER_FILE = 20000


def sha1_head(path, limit=1 << 20):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        h.update(f.read(limit))
    return h.hexdigest()


def iter_records(path, ext):
    """(status, records) — records는 dict 목록(최대 MAX_RECORDS_PER_FILE)."""
    records = []
    if ext == ".json":
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            return f"broken:{type(e).__name__}", records
        items = data if isinstance(data, list) else [data]
        records = [r for r in items[:MAX_RECORDS_PER_FILE] if isinstance(r, dict)]
        return "ok", records
    bad = 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except Exception:
                bad += 1
                continue
            if isinstance(obj, dict) and len(records) < MAX_RECORDS_PER_FILE:
                records.append(obj)
    return ("ok" if bad == 0 else f"broken_lines:{bad}"), records


def count_lines(path):
    n = 0
    with open(path, "rb") as f:
        for _ in f:
            n += 1
    return n


def empty_value(v):
    return v is None or v == "" or v == [] or v == {}


def main(root):
    report = {
        "scanner": VERSION,
        "root": root,
        "scanned_at": datetime.now().isoformat(timespec="seconds"),
        "files": 0,
        "bytes": 0,
        "by_ext": collections.Counter(),
        "by_day": collections.Counter(),
        "by_top_folder": collections.Counter(),
        "empty_files": [],
        "temp_leftovers": [],
        "broken": [],
        "name_patterns": collections.Counter(),
        "dup_groups": [],
        "largest": [],
        "size_outliers_small": [],
        "newest_mtime": None,
        "oldest_mtime": None,
        "records": 0,
        "text_lines": 0,
    }
    if not os.path.isdir(root):
        report["error"] = "ROOT_NOT_FOUND"
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
        return
    heads = collections.defaultdict(list)
    sizes_by_ext = collections.defaultdict(list)
    field_seen = collections.Counter()
    field_empty = collections.Counter()
    key_field = None
    key_values = collections.Counter()
    days = set()
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
            top = rel.split(os.sep)[0] if os.sep in rel else "(root)"
            report["by_top_folder"][top] += 1
            mt = datetime.fromtimestamp(st.st_mtime)
            days.add(mt.date())
            report["by_day"][mt.strftime("%Y-%m-%d")] += 1
            iso = mt.isoformat(timespec="seconds")
            report["newest_mtime"] = max(report["newest_mtime"] or iso, iso)
            report["oldest_mtime"] = min(report["oldest_mtime"] or iso, iso)
            report["name_patterns"][re.sub(r"\d", "#", name)] += 1
            if st.st_size == 0:
                report["empty_files"].append(rel)
            if TEMP_PAT.search(name):
                report["temp_leftovers"].append(rel)
            sizes_by_ext[ext].append((st.st_size, rel))
            if ext in (".json", ".jsonl", ".ndjson") and st.st_size > 0:
                status, recs = iter_records(path, ".json" if ext == ".json" else ".jsonl")
                report["records"] += len(recs)
                if status != "ok":
                    report["broken"].append([rel, status])
                for r in recs:
                    for k, v in r.items():
                        field_seen[k] += 1
                        if empty_value(v):
                            field_empty[k] += 1
                    if key_field is None:
                        key_field = next((k for k in KEY_CANDIDATES if k in r), None)
                    if key_field and key_field in r and not empty_value(r[key_field]):
                        key_values[str(r[key_field])] += 1
            elif ext in (".txt", ".csv", ".tsv", ".md") and st.st_size > 0:
                report["text_lines"] += count_lines(path)
            if 0 < st.st_size <= 50 << 20:
                heads[(st.st_size, sha1_head(path))].append(rel)
    # 파일 단위 중복
    report["dup_groups"] = [v for v in heads.values() if len(v) > 1][:50]
    # 크기 이상치: 같은 확장자 중앙값의 10% 미만 (5개 이상일 때)
    for ext, items in sizes_by_ext.items():
        nonzero = [s for s, _ in items if s > 0]
        if len(nonzero) >= 5:
            med = statistics.median(nonzero)
            report["size_outliers_small"] += [[rel, s, int(med)] for s, rel in items if 0 < s < med * 0.1]
    report["size_outliers_small"] = report["size_outliers_small"][:50]
    all_sizes = [x for items in sizes_by_ext.values() for x in items]
    report["largest"] = [[s, r] for s, r in sorted(all_sizes, reverse=True)[:10]]
    # 날짜 공백: 가장 오래된 날 ~ 가장 최근 날 사이 파일이 하나도 없는 날
    if days:
        d, end, gaps = min(days), max(days), []
        while d <= end:
            if d not in days:
                gaps.append(d.isoformat())
            d += timedelta(days=1)
        report["day_gaps"] = gaps[:60]
        report["day_gaps_count"] = len(gaps)
        report["days_since_newest"] = (date.today() - end).days
    # 레코드 필드 채움률
    report["record_fields"] = {
        k: {"seen": n, "empty_ratio": round(field_empty[k] / n, 3)}
        for k, n in field_seen.most_common(40)
    }
    report["record_key_field"] = key_field
    dups = {k: c for k, c in key_values.items() if c > 1}
    report["record_dup_keys_count"] = len(dups)
    report["record_dup_extra_rows"] = sum(c - 1 for c in dups.values())
    report["by_ext"] = dict(report["by_ext"].most_common())
    report["by_day"] = dict(sorted(report["by_day"].items())[-30:])
    report["by_top_folder"] = dict(report["by_top_folder"].most_common(30))
    report["name_patterns"] = dict(report["name_patterns"].most_common(20))
    for key in ("empty_files", "temp_leftovers", "broken"):
        report[key + "_count"] = len(report[key])
        report[key] = report[key][:50]
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else r"K:\스크롤 데이터")
