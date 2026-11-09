"""
영상별 특징 추출 + 교차 검증 + 터진 영상 vs 나머지 비교

터짐 기준(채널 크기 보정): 조회수 / 구독자 수 (구독자 비공개면 시간당 조회수로 대체).
주제 안에서 상위 25%를 'HIT'로 보고, 특징 평균 차이를 가설(CANDIDATE)로 남긴다.
표본이 8개 미만이면 비교하지 않고 '표본 부족'으로 둔다.
"""

import statistics

from .textutil import numbers, tokens

MIN_SAMPLE = 8


# ---------- 개별 특징 ----------
def title_features(title):
    return {
        "title_len": len(title),
        "title_has_number": int(any(c.isdigit() for c in title)),
        "title_has_question": int("?" in title or "까" in title[-3:]),
        "title_has_bracket": int(any(b in title for b in "[]【】()")),
        "title_has_exclaim": int("!" in title),
    }


def thumbnail_features(path):
    """밝기·대비·채도·윤곽 밀도(글자 많은 썸네일일수록 높음). Pillow 필요."""
    if not path:
        return {}
    try:
        from PIL import Image, ImageFilter, ImageStat
        img = Image.open(path).convert("RGB").resize((320, 180))
    except Exception:
        return {}
    gray = img.convert("L")
    hsv = img.convert("HSV")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    return {
        "thumb_brightness": round(ImageStat.Stat(gray).mean[0], 1),
        "thumb_contrast": round(ImageStat.Stat(gray).stddev[0], 1),
        "thumb_saturation": round(ImageStat.Stat(hsv).mean[1], 1),
        "thumb_edge_density": round(ImageStat.Stat(edges).mean[0], 1),
    }


def script_features(cues, duration_sec):
    if not cues:
        return {}
    text = " ".join(t for _, t in cues)
    words = text.split()
    minutes = max((duration_sec or (cues[-1][0] + 3)) / 60, 0.1)
    hook = " ".join(t for s, t in cues if s <= 15)
    return {
        "script_words": len(words),
        "script_wpm": round(len(words) / minutes, 1),
        "hook_15s": hook[:200],
        "hook_has_number": int(any(c.isdigit() for c in hook)),
        "hook_has_question": int("?" in hook or "까" in hook),
        "script_numbers": len(numbers(text)),
    }


def performance(rec):
    views, subs, age = rec.get("views"), rec.get("subscribers"), rec.get("age_hours") or 0
    perf = {
        "views_per_hour": round(views / max(age, 1), 1) if views is not None else None,
        "outlier_ratio": round(views / subs, 3) if views is not None and subs else None,
        "engagement": None,
    }
    if views:
        likes, comments = rec.get("likes") or 0, rec.get("comments") or 0
        perf["engagement"] = round((likes + comments) / views, 4)
    return perf


# ---------- 교차 검증 ----------
def cross_check(rec, topic, cues):
    """주제·제목·설명·대본·뉴스 숫자가 서로 맞는지."""
    kw = set(topic["keywords"])
    title_t = set(tokens(rec["title"]))
    desc_t = set(tokens(rec.get("description", "")))
    script_text = " ".join(t for _, t in cues) if cues else ""
    script_t = set(tokens(script_text))
    first60 = set(tokens(" ".join(t for s, t in cues if s <= 60))) if cues else set()
    title_core = {t for t in title_t if len(t) >= 2}
    result = {
        "topic_in_title": bool(kw & title_t),
        "topic_in_desc": bool(kw & desc_t),
        "topic_in_script": bool(kw & script_t) if cues else None,
        # 제목 단어가 첫 60초에 하나도 안 나오면 낚시성 의심
        "title_paid_off_60s": (len(title_core & first60) / len(title_core) if title_core else None) if cues else None,
        "news_numbers_in_script": None,
    }
    if cues and topic.get("news_numbers"):
        flat = script_text.replace(" ", "").replace(",", "")
        hits = [n for n in topic["news_numbers"] if n.replace(",", "") in flat]
        result["news_numbers_in_script"] = f"{len(hits)}/{len(topic['news_numbers'])}"
    flags = []
    if not result["topic_in_title"] and not result["topic_in_desc"]:
        flags.append("주제 불일치(검색에만 걸린 영상)")
    if result["title_paid_off_60s"] is not None and result["title_paid_off_60s"] < 0.2:
        flags.append("제목 약속이 첫 60초에 안 나옴")
    result["flags"] = flags
    return result


def enrich(rec, topic, cues):
    rec.update(performance(rec))
    rec.update(title_features(rec["title"]))
    rec.update(thumbnail_features(rec.get("thumbnail_file")))
    rec.update(script_features(cues, rec.get("duration_sec")))
    rec["format"] = "shorts" if (rec.get("duration_sec") or 0) <= 180 else "longform"
    rec["cross_check"] = cross_check(rec, topic, cues)
    return rec


# ---------- 터진 영상 vs 나머지 ----------
COMPARE_KEYS = [
    "title_len", "title_has_number", "title_has_question", "title_has_bracket",
    "thumb_brightness", "thumb_contrast", "thumb_saturation", "thumb_edge_density",
    "script_wpm", "hook_has_number", "hook_has_question", "duration_sec", "engagement",
]


def _hit_metric(rec):
    return rec["outlier_ratio"] if rec.get("outlier_ratio") is not None else rec.get("views_per_hour")


def hit_analysis(records):
    # 주제와 안 맞는 영상(검색에만 걸린 것)은 패턴 근거에서 뺀다
    usable = [r for r in records
              if not any(f.startswith("주제 불일치") for f in r.get("cross_check", {}).get("flags", []))]
    excluded = len(records) - len(usable)
    scored = [r for r in usable if _hit_metric(r) is not None]
    if len(scored) < MIN_SAMPLE:
        return {"status": f"표본 부족 ({len(scored)}개 < {MIN_SAMPLE}, 주제 불일치 제외 {excluded}개) — 비교 보류",
                "rows": []}
    scored.sort(key=_hit_metric, reverse=True)
    cutoff = _hit_metric(scored[max(2, len(scored) // 4) - 1])
    for r in scored:
        r["is_hit"] = _hit_metric(r) >= cutoff   # 경계값과 같은 영상은 모두 HIT
    hits = [r for r in scored if r["is_hit"]]
    rest = [r for r in scored if not r["is_hit"]]
    if not rest:
        return {"status": "모든 영상 성과가 같아 비교 불가", "rows": []}
    rows = []
    for key in COMPARE_KEYS:
        hv = [r[key] for r in hits if isinstance(r.get(key), (int, float))]
        rv = [r[key] for r in rest if isinstance(r.get(key), (int, float))]
        if len(hv) < 2 or len(rv) < 2:
            continue
        hm, rm = statistics.mean(hv), statistics.mean(rv)
        spread = statistics.pstdev(hv + rv) or 1
        digits = 4 if max(abs(hm), abs(rm)) < 1 else 2
        rows.append({
            "feature": key, "hit_mean": round(hm, digits), "rest_mean": round(rm, digits),
            "effect": round((hm - rm) / spread, 2), "n_hit": len(hv), "n_rest": len(rv),
        })
    rows.sort(key=lambda x: abs(x["effect"]), reverse=True)
    return {"status": f"HIT {len(hits)} / 나머지 {len(rest)} (주제 불일치 제외 {excluded}개)", "rows": rows}
