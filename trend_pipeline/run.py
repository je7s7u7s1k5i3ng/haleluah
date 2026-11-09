"""
실행 진입점

사용 (프로그램 폴더에서):
    python -m trend_pipeline.run 오늘 경제 터진 주제로 수집해줘
    python -m trend_pipeline.run --category 경제 --top-topics 5
    python -m trend_pipeline.run --category 경제 --news-only      # 유튜브 없이 주제만

결과: <프로그램 폴더>\\결과\\YYYYMMDD_HHMM_<카테고리>\\
    hot_topics.json, videos.jsonl, thumbnails\\, transcripts\\, 보고서.md, manifest.json
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

from . import VERSION
from .analyze import enrich, hit_analysis
from .config import CATEGORIES, load_settings, paths
from .hot_topics import HotTopicFinder
from .report import build
from .store import Store
from .transcripts import TranscriptCollector, available as transcripts_available
from .youtube import QuotaExceeded, YouTubeCollector

KST = timezone(timedelta(hours=9))
DEFAULT_CATEGORY = "경제"


def detect_category(text):
    for name in CATEGORIES:
        if name in text:
            return name
    return None


def parse_args(argv):
    ap = argparse.ArgumentParser(description="터진 주제 → 유튜브 교차 분석")
    ap.add_argument("request", nargs="*", help="자연어 요청 (예: 오늘 경제 터진 주제로 수집해줘)")
    ap.add_argument("--category", choices=list(CATEGORIES))
    ap.add_argument("--top-topics", type=int)
    ap.add_argument("--videos-per-topic", type=int)
    ap.add_argument("--news-only", action="store_true")
    ap.add_argument("--no-transcripts", action="store_true")
    ap.add_argument("--base-dir", help="프로그램 폴더 (기본: 이 파일이 있는 폴더)")
    args = ap.parse_args(argv)
    if not args.category and not args.request:
        args.category = DEFAULT_CATEGORY     # 아무것도 안 넣고 실행하면 경제
    if not args.category:
        args.category = detect_category(" ".join(args.request))
    if not args.category:
        ap.error(f"카테고리를 알 수 없습니다. 다음 중 하나를 넣어 주세요: {', '.join(CATEGORIES)}")
    return args


def main(argv=None, session=None, now=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    p = paths(args.base_dir)
    settings = load_settings(args.base_dir)
    if args.top_topics:
        settings["top_topics"] = args.top_topics
    if args.videos_per_topic:
        settings["videos_per_topic"] = args.videos_per_topic

    now = now or datetime.now(timezone.utc)
    stamp = now.astimezone(KST).strftime("%Y%m%d_%H%M")
    out = p["results"] / f"{stamp}_{args.category}"
    (out / "thumbnails").mkdir(parents=True, exist_ok=True)
    (out / "transcripts").mkdir(exist_ok=True)
    log_file = open(p["logs"] / f"{stamp}.log", "a", encoding="utf-8")

    def log(msg):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        print(line)
        log_file.write(line + "\n")

    store = Store(p["db"])
    status = {"버전": VERSION, "카테고리": args.category}
    try:
        log(f"=== {args.category} 터진 주제 수집 시작 ===")
        finder = HotTopicFinder(store, settings, session=session, log=log)
        topics = finder.find(args.category, settings["top_topics"], now=now)
        status.update({f"뉴스 {k}": v for k, v in finder.signal_status.items()})
        (out / "hot_topics.json").write_text(json.dumps(topics, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"터지는 주제 {len(topics)}개: " + " / ".join(t["label"] for t in topics))

        videos_by_topic, analysis_by_topic = {}, {}
        key = settings.get("youtube_api_key")
        if args.news_only:
            status["유튜브"] = "건너뜀(--news-only)"
        elif not key:
            status["유튜브"] = "HOLD(YOUTUBE_API_KEY 없음)"
        else:
            yt = YouTubeCollector(key, settings, session=session, log=log)
            tc = None
            if args.no_transcripts or not settings.get("transcripts", True):
                status["대본"] = "건너뜀"
            elif not transcripts_available():
                status["대본"] = "HOLD(yt-dlp 미설치)"
            else:
                tc = TranscriptCollector(out / "transcripts", settings, log=log)
            with open(out / "videos.jsonl", "w", encoding="utf-8") as vf:
                for t in topics:
                    try:
                        recs = yt.collect_topic(t, out / "thumbnails", now=now)
                    except QuotaExceeded:
                        status["유튜브"] = f"할당량 초과로 중단 (사용 {yt.units_used}단위)"
                        log("[유튜브] 할당량 초과 — 남은 주제는 HOLD")
                        break
                    except Exception as e:
                        log(f"[유튜브] '{t['label']}' 실패: {e}")
                        continue
                    for r in recs:
                        cues = tc.fetch(r["video_id"]) if tc else None
                        r["transcript_available"] = bool(cues)
                        enrich(r, t, cues)
                    analysis_by_topic[t["label"]] = hit_analysis(recs)
                    videos_by_topic[t["label"]] = recs
                    for r in recs:
                        vf.write(json.dumps(r, ensure_ascii=False) + "\n")
                    log(f"[유튜브] '{t['label']}' 영상 {len(recs)}개")
            status.setdefault("유튜브", f"OK (사용 {yt.units_used}단위)")
            if tc:
                status["대본"] = "중단(HOLD)" if tc.stopped else "OK"

        report = build(args.category, now.astimezone(KST).strftime("%Y-%m-%d %H:%M"),
                       topics, videos_by_topic, analysis_by_topic, status)
        (out / "보고서.md").write_text(report, encoding="utf-8")
        manifest = {
            "version": VERSION, "category": args.category, "run_at": now.isoformat(),
            "output_dir": str(out), "topics": len(topics),
            "videos": sum(len(v) for v in videos_by_topic.values()), "status": status,
            "state": "CANDIDATE",
        }
        (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"완료 → {out / '보고서.md'}")
        return out
    finally:
        store.close()
        log_file.close()


if __name__ == "__main__":
    main()
