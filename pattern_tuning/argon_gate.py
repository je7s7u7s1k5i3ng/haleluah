# -*- coding: utf-8 -*-
"""
아르곤(제미나이 울트라) 보고서 검증 관문 — 성공 패턴으로 저장하기 전에 반드시 통과

사용:
    python argon_gate.py 보고서.md                 # 1개 판정
    python argon_gate.py --folder <보고서 폴더>     # 폴더 전체 판정 + 요약
    python argon_gate.py --folder <폴더> --out 판정결과.json

읽기 전용이다. 파일을 옮기거나 고치지 않는다. 판정 결과만 출력한다.

판정:
    PASS  — 성공 패턴 후보로 저장 가능 (여전히 CANDIDATE)
    WARN  — 내용은 쓸 수 있으나 정리 필요(화면 잡음·끝 잘림)
    FAIL  — 실패 기록소로. 성공 패턴·KB·기준선 점수에 넣지 않는다
"""

import argparse
import collections
import json
import re
import sys
from pathlib import Path

VERSION = "1.0.0"

# 제미나이가 입력이 망가졌다고 스스로 말하는 표현
MODEL_ADMITS = [
    "깨짐", "깨지면서", "절단", "잘린 상태", "잘려", "누락", "입력 대기", "추가 대기",
    "붙여넣어 주시면", "붙여넣어 주시면", "재전송", "원문 전달 시", "대본 입력 시 업데이트",
    "추정 의제", "데이터 대기", "다시 보내", "복원·통합", "정밀 복원",
]
# 화면 껍데기(사이드바·안내문)가 같이 긁힌 흔적
UI_CHROME = [
    "새 채팅", "라이브러리", "Gemini와의 대화", "모든 노트북", "새 노트북",
    "주의 사항", "Gemini는 AI이며", "Google 약관 및 개인정보처리방침",
]
_CLUSTER = re.compile(r"클러스터\s*#?\s*(\d{1,3})\s*/\s*(\d{1,3})")
_NUM = re.compile(r"\d[\d,.]*\s*(?:%|원|달러|조|억|만|bp|배|년|개월)")
_SECTION = re.compile(r"(?m)^\s*([123])\.\s*\[")
# 한 단어 안에 한글과 영문이 뒤섞인 덩어리(키 입력 중 한/영 전환이 꼬일 때 생김)
_MIXED = re.compile(r"[A-Za-z]+[가-힣]+[A-Za-z]+|[가-힣]+[A-Za-z]+[가-힣]+")


def _split(text):
    """머리말(메타) / 프롬프트 메아리 / 응답 본문으로 나눈다."""
    head, _, rest = text.partition("\n---")
    marker = rest.find("Gemini와의 대화")
    body = rest[marker:] if marker >= 0 else rest
    # 프롬프트 메아리: '대본 원문 발췌' 가 있는 줄들
    echo_lines = [l for l in body.splitlines() if "원문 발췌" in l or "아래는 최근" in l]
    echo = "\n".join(echo_lines)
    answer = body
    for l in echo_lines:
        answer = answer.replace(l, "")
    return head, echo, answer


def check(text):
    head, echo, answer = _split(text)
    findings = []

    # G1 입력 손상: 프롬프트 메아리 속 한/영이 한 덩어리에 뒤섞인 토큰, 영숫자 사이에 낀 기호
    tokens_ = echo.split()
    mixed = [t for t in tokens_ if _MIXED.search(t) or (re.search(r"[가-힣]", t) and re.search(r"[A-Za-z]", t)
                                                       and not re.match(r"^[A-Za-z]+[가-힣]{1,3}[.,)]?$", t))]
    junk = [t for t in tokens_ if re.search(r"[A-Za-z0-9][;&#\]][A-Za-z0-9]", t)]
    if len(mixed) + len(junk) >= 3:
        findings.append(("FAIL", "G1_INPUT_CORRUPT",
                         f"프롬프트 원문이 깨져 전달됨 (뒤섞인 덩어리 {len(mixed)}개, 기호 낀 덩어리 {len(junk)}개)"))

    # G2 모델이 누락·깨짐을 스스로 밝힘 / 빈칸 채우기 문구
    admits = sorted({p for p in MODEL_ADMITS if p in answer})
    if len(admits) >= 2:
        findings.append(("FAIL", "G2_MODEL_ADMITS_MISSING",
                         "응답이 입력 누락을 인정하고 틀만 작성: " + ", ".join(admits[:5])))

    # G3 다른 클러스터 응답이 저장됨 (머리말 번호 ≠ 프롬프트 번호)
    head_c = _CLUSTER.search(head)
    echo_c = _CLUSTER.findall(echo + "\n" + answer[:3000])
    if head_c and echo_c:
        want = head_c.group(1).lstrip("0")
        got = {n.lstrip("0") for n, _ in echo_c}
        if want not in got:
            findings.append(("FAIL", "G3_WRONG_THREAD",
                             f"머리말은 #{want}인데 본문은 #{'/#'.join(sorted(got))} 대화를 저장함"))
    chan_line = re.search(r"분석 채널\**:\s*`([^`]+)`", head)
    if chan_line and echo:
        chans = [c.strip() for c in chan_line.group(1).split(",") if c.strip()]
        hits = [c for c in chans if c in echo or c in answer]
        if chans and len(hits) <= len(chans) // 3:
            findings.append(("FAIL", "G3_CHANNEL_MISMATCH",
                             f"머리말 채널 {len(chans)}개 중 본문에 나온 것 {len(hits)}개"))

    # G4 화면 잡음
    chrome = [c for c in UI_CHROME if c in text]
    if len(chrome) >= 3:
        findings.append(("WARN", "G4_UI_CHROME", "사이드바·안내문이 함께 저장됨: " + ", ".join(chrome[:4])))

    # G5 끝 잘림 / 섹션 누락
    sections = set(_SECTION.findall(answer))
    if not {"1", "2", "3"} <= sections:
        findings.append(("WARN", "G5_SECTION_MISSING", f"섹션 {sorted(sections) or '없음'}만 있음 (1·2·3 필요)"))
    tail = text.rstrip()[-30:]
    if tail and not re.search(r"[.!?다요)\]」”\"]\s*$", tail.split("Gemini")[0] or tail):
        findings.append(("WARN", "G5_TRUNCATED_TAIL", f"끝이 잘림: …{tail[-15:]}"))

    # G6 근거 없는 수치: 입력이 망가졌는데 응답에 프롬프트에 없던 숫자가 많음
    if any(code in ("G1_INPUT_CORRUPT", "G2_MODEL_ADMITS_MISSING") for _, code, _ in findings):
        echo_nums = {n.replace(" ", "") for n in _NUM.findall(echo)}
        new_nums = {n.replace(" ", "") for n in _NUM.findall(answer)} - echo_nums
        if len(new_nums) >= 5:
            findings.append(("FAIL", "G6_UNGROUNDED_NUMBERS",
                             f"입력에 없던 수치 {len(new_nums)}개를 생성 (예: {', '.join(sorted(new_nums)[:4])})"))

    # G7 실패인데 기준선 점수가 찍혀 있음
    stamp = re.search(r"기준선\**:\s*`([^`]+)`", head)
    verdict = "FAIL" if any(s == "FAIL" for s, _, _ in findings) else ("WARN" if findings else "PASS")
    if stamp and verdict == "FAIL":
        findings.append(("FAIL", "G7_SCORE_ON_FAILURE", f"실패 보고서에 기준선 표시: {stamp.group(1)}"))

    return {
        "verdict": verdict,
        "cluster": head_c.group(1) if head_c else None,
        "findings": [{"level": s, "code": c, "detail": d} for s, c, d in findings],
    }


def scan_folder(folder):
    results = {}
    for p in sorted(Path(folder).rglob("*.md")):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            results[str(p)] = {"verdict": "HOLD", "findings": [{"level": "HOLD", "code": "READ_ERROR", "detail": str(e)}]}
            continue
        if "클러스터" not in text and "Argon" not in text:
            continue
        results[str(p)] = check(text)
    by_cluster = collections.defaultdict(list)
    for path, r in results.items():
        if r.get("cluster"):
            by_cluster[r["cluster"]].append(path)
    dups = {c: ps for c, ps in by_cluster.items() if len(ps) > 1}
    codes = collections.Counter(f["code"] for r in results.values() for f in r["findings"])
    summary = {
        "gate_version": VERSION,
        "files": len(results),
        "verdicts": dict(collections.Counter(r["verdict"] for r in results.values())),
        "codes": dict(codes.most_common()),
        "duplicate_clusters": dups,
        "pass_rate": round(sum(r["verdict"] == "PASS" for r in results.values()) / len(results), 3) if results else None,
    }
    return summary, results


def main(argv=None):
    ap = argparse.ArgumentParser(description="아르곤 보고서 검증 관문")
    ap.add_argument("file", nargs="?")
    ap.add_argument("--folder")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    if a.folder:
        summary, results = scan_folder(a.folder)
        payload = {"summary": summary, "results": results}
    elif a.file:
        payload = check(Path(a.file).read_text(encoding="utf-8", errors="replace"))
    else:
        ap.error("파일 또는 --folder 를 넣어 주세요")
    out = json.dumps(payload, ensure_ascii=False, indent=2)
    if a.out:
        Path(a.out).write_text(out, encoding="utf-8")
    print(out)
    verdict = payload["summary"]["verdicts"] if a.folder else payload["verdict"]
    return 1 if (verdict == "FAIL" or (isinstance(verdict, dict) and verdict.get("FAIL"))) else 0


if __name__ == "__main__":
    sys.exit(main())
