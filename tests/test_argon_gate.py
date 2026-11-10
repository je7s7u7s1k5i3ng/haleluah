"""argon_gate 테스트 — 실제 실패 보고서 3종의 증상을 재현한 표본 + 정상 표본"""

import json

from pattern_tuning import argon_gate

HEAD = """# 🧠 [실전 경제 클러스터 #{n}/19] {chans} 외 5편 통합 — Gemini Ultra (Argon) 심층리서치 & 태스크 통합 보고서

- **생성 일시**: `2026-10-30 06:15:19 KST`
- **적용 기준선**: `SLAVE-BASELINE-GEN8 (99.97점)`
- **분석 채널**: `{chans}`
- **수집 글자수**: `6,949자`

---
"""

CHROME = "Gemini\n\n새 채팅\n라이브러리\n이미지\n\n새 노트북\n모든 노트북\n대본 데이터 누락 알림\nGemini와의 대화\n"

FOOTER = "\n주의 사항\nGemini는 AI이며 실수를 할 수 있습니다. Google 약관 및 개인정보처리방침이 적용됩니다.\n"


def make(n, chans, echo_n, echo_chans, echo_text, answer):
    echo = (f"[실전 경제 클러스터 #{echo_n}/19] {echo_chans} 외 5편 통합] | 아래는 최근 10일 이내 수집된 경제 유튜브 5편 | "
            f"### 소스 1. [{echo_chans.split(',')[0]}] 제목 | - 대본 원문 발췌: {echo_text}")
    return HEAD.format(n=n, chans=chans) + CHROME + echo + "\n\n" + answer + FOOTER


BROKEN_ECHO = ("Russia's spent nearly five years now and despite losses according to some estimates1tr itd as# "
               "3hgMh;wonhuardi&h 미 말선반.자 국향 고습와돈약니A자.가 분결 내고증이 셨고.A인")
GOOD_ECHO = "환율이 1,450원을 넘었고 코스피는 3% 하락했습니다. 반도체 수출은 20% 늘었습니다."

FAKE_ANSWER = """프롬프트가 소스 1 도중 문자열이 깨지면서 나머지 데이터가 잘린 상태로 전달되었습니다.
나머지 소스를 붙여넣어 주시면 완성해 드리겠습니다.
1. [NotebookLM 교차 팩트체크]
소스 2 (대본 데이터 입력 대기) 미 부채 35조 달러, 이자 1조 달러, 환율 1,400원, 금리 4.5%, 성장 15%, CAPEX 2,000억 달러
2. [심층리서치]
...
3. [태스크]
훅 3선입니다.
"""

GOOD_ANSWER = """1. [NotebookLM 교차 팩트체크]
환율 1,450원, 코스피 3% 하락, 반도체 수출 20% 증가가 소스 1·2에서 일치합니다.
2. [심층리서치]
환율 상승이 수입 물가를 밀어 올리는 구조입니다.
3. [태스크]
훅 1: 환율 1,450원이 내 장바구니에 오는 시간은 석 달입니다.
"""


def codes(r):
    return {f["code"] for f in r["findings"]}


def test_cluster18_style_corrupt_input_and_wrong_channels():
    text = make(18, "Eurodollar University, Everything Money, 손에잡히는경제",
                "?", "RealLifeLore, 내일은 투자왕 - 김단테", BROKEN_ECHO, FAKE_ANSWER).replace("#?/19", "")
    r = argon_gate.check(text)
    assert r["verdict"] == "FAIL"
    assert {"G1_INPUT_CORRUPT", "G2_MODEL_ADMITS_MISSING", "G3_CHANNEL_MISMATCH",
            "G6_UNGROUNDED_NUMBERS", "G7_SCORE_ON_FAILURE"} <= codes(r)


def test_cluster08_style_wrong_thread_number():
    text = make(8, "Patrick Boyle, TLDR Business, The Economist", 1,
                "ColdFusion, Financial Audit with Caleb Hammer, Minority Mindset", BROKEN_ECHO, FAKE_ANSWER)
    r = argon_gate.check(text)
    assert "G3_WRONG_THREAD" in codes(r)
    assert any("#8" in f["detail"] and "#1" in f["detail"] for f in r["findings"] if f["code"] == "G3_WRONG_THREAD")


def test_good_report_passes_with_only_cleanup_warnings():
    chans = "슈카월드, 언더스탠딩, 손에잡히는경제"
    text = make(5, chans, 5, chans, GOOD_ECHO, GOOD_ANSWER)
    r = argon_gate.check(text)
    assert r["verdict"] in ("PASS", "WARN")
    assert not [f for f in r["findings"] if f["level"] == "FAIL"]
    clean = text.split("주의 사항")[0]
    clean = clean.replace(CHROME, "Gemini와의 대화\n")
    assert argon_gate.check(clean)["verdict"] == "PASS"


def test_folder_scan_counts_duplicates_and_pass_rate(tmp_path):
    chans = "슈카월드, 언더스탠딩, 손에잡히는경제"
    (tmp_path / "ARGON_GEN8_CLUSTER_14_a.md").write_text(
        make(14, chans, 9, "HowMoneyWorks, Mark Tilbury, Minority Mindset", BROKEN_ECHO, FAKE_ANSWER), encoding="utf-8")
    (tmp_path / "ARGON_GEN8_CLUSTER_14_b.md").write_text(
        make(14, chans, 14, chans, GOOD_ECHO, GOOD_ANSWER), encoding="utf-8")
    (tmp_path / "기타메모.md").write_text("관계없는 메모", encoding="utf-8")
    summary, results = argon_gate.scan_folder(tmp_path)
    assert summary["files"] == 2
    assert summary["verdicts"].get("FAIL") == 1
    assert "14" in summary["duplicate_clusters"]
    assert summary["pass_rate"] < 1
    out = tmp_path / "판정.json"
    rc = argon_gate.main(["--folder", str(tmp_path), "--out", str(out)])
    assert rc == 1 and json.loads(out.read_text(encoding="utf-8"))["summary"]["files"] == 2
