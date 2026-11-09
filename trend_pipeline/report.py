"""보고서(보고서.md) 작성 — 숫자만 쓰고, 측정 못 한 칸은 HOLD로 둔다."""

_FEATURE_KO = {
    "title_len": "제목 글자 수", "title_has_number": "제목에 숫자", "title_has_question": "제목 질문형",
    "title_has_bracket": "제목 괄호", "thumb_brightness": "썸네일 밝기", "thumb_contrast": "썸네일 대비",
    "thumb_saturation": "썸네일 채도", "thumb_edge_density": "썸네일 글자·윤곽 밀도",
    "script_wpm": "말 속도(분당 단어)", "hook_has_number": "첫 15초 숫자", "hook_has_question": "첫 15초 질문",
    "duration_sec": "영상 길이(초)", "engagement": "참여율",
}


def _v(x):
    return "HOLD" if x is None else x


def build(category, run_day, topics, videos_by_topic, analysis_by_topic, status):
    L = [f"# {run_day} {category} 터진 주제 × 유튜브 분석", "",
         "> 상태: CANDIDATE — 아래 비교는 가설이다. 실제 업로드 성과로 검증 전에는 기준선으로 쓰지 않는다.", ""]
    L += ["## 수집 상태", "", "| 항목 | 상태 |", "|---|---|"]
    for k, v in status.items():
        L.append(f"| {k} | {v} |")
    L += ["", "## 1. 오늘 터지는 주제 (뉴스 측정값)", "",
          "| 순위 | 주제 | 점수 | 기사 수 | 매체 수 | 급상승 | 검색 급상승 | 대표 헤드라인 |",
          "|---|---|---|---|---|---|---|---|"]
    for i, t in enumerate(topics, 1):
        L.append(f"| {i} | {t['label']} | {t['hot_score']} | {t['S_articles']} | {t['S_outlets']} | "
                 f"{_v(t['S_burst'])} | {_v(t['S_search'])} | {t['headlines'][0][:40]} |")
    for t in topics:
        vids = videos_by_topic.get(t["label"], [])
        L += ["", f"## 2. [{t['label']}] 유튜브 영상 {len(vids)}개", ""]
        if not vids:
            L.append("영상 수집 HOLD (유튜브 API 키 없음 또는 할당량 초과)")
            continue
        L += ["| 터짐 | 제목 | 조회수 | 구독자 | 조회/구독 | 시간당 조회 | 형식 | 교차 검증 경고 |",
              "|---|---|---|---|---|---|---|---|"]
        for r in sorted(vids, key=lambda x: x.get("outlier_ratio") or 0, reverse=True):
            flags = ", ".join(r["cross_check"]["flags"]) or "-"
            L.append(f"| {'🔥' if r.get('is_hit') else ''} | [{r['title'][:38]}]({r['url']}) | {_v(r['views'])} | "
                     f"{_v(r['subscribers'])} | {_v(r['outlier_ratio'])} | {_v(r['views_per_hour'])} | {r['format']} | {flags} |")
        hooks = [r for r in vids if r.get("is_hit") and r.get("hook_15s")]
        if hooks:
            L += ["", "**터진 영상의 첫 15초 대본**", ""]
            for r in hooks[:3]:
                L.append(f"- {r['title'][:30]} → “{r['hook_15s'][:120]}”")
        a = analysis_by_topic.get(t["label"], {})
        L += ["", f"**터진 영상 vs 나머지** — {a.get('status', 'HOLD')}", ""]
        if a.get("rows"):
            L += ["| 특징 | 터진 영상 평균 | 나머지 평균 | 차이 크기 |", "|---|---|---|---|"]
            for row in a["rows"][:8]:
                L.append(f"| {_FEATURE_KO.get(row['feature'], row['feature'])} | {row['hit_mean']} | "
                         f"{row['rest_mean']} | {row['effect']:+} |")
    L += ["", "## 3. 다음 할 일", "",
          "- 차이 크기 ±0.5 이상인 특징만 가설로 옮겨 실제 업로드로 시험한다(A/B).",
          "- 교차 검증 경고가 붙은 영상은 패턴 근거에서 뺀다.",
          "- 대본·썸네일은 분석용 로컬 보관만 한다. 재업로드·재배포 금지.", ""]
    return "\n".join(L)
