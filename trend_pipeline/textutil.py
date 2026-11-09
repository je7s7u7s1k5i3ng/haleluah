"""한국어 제목 정리·토큰화·유사도 (외부 형태소 분석기 없이 동작하는 가벼운 버전)"""

import re

# 흔한 조사·어미 꼬리 (긴 것부터 떼어낸다)
_SUFFIXES = sorted(
    ["에서는", "으로는", "에게서", "까지", "부터", "에서", "으로", "에게", "보다", "처럼",
     "은", "는", "이", "가", "을", "를", "의", "에", "로", "와", "과", "도", "만", "랑"],
    key=len, reverse=True,
)
_STOPWORDS = {
    "속보", "단독", "종합", "기자", "뉴스", "오늘", "어제", "내일", "올해", "지난해", "관련",
    "위해", "대한", "통해", "따라", "이번", "그리고", "하지만", "있다", "없다", "했다", "한다",
    "된다", "됐다", "이다", "포토", "영상", "사진", "인터뷰", "전망", "분석",
}
_NUM_UNIT = re.compile(r"\d[\d,.]*\s*(?:%|퍼센트|원|달러|조|억|만|천|배|bp|포인트|p)?")


def clean_title(title):
    """'제목 - 언론사' → ('제목', '언론사'). 대괄호 말머리 제거."""
    title = (title or "").strip()
    outlet = ""
    if " - " in title:
        title, outlet = title.rsplit(" - ", 1)
    title = re.sub(r"^\s*[\[【(<][^\]】)>]{1,12}[\]】)>]\s*", "", title)
    return title.strip(), outlet.strip()


def _forms(token):
    """원형 + 조사 뗀 형태. 형태소 분석기가 없어 '물가'의 '가'처럼 명사 끝 글자를
    조사로 오인할 수 있으므로 한 글자 조사는 두 형태를 모두 남긴다."""
    for s in _SUFFIXES:
        if len(token) > len(s) + 1 and token.endswith(s):
            stripped = token[: -len(s)]
            return [stripped] if len(s) >= 2 else [token, stripped]
    return [token]


def tokens(text):
    """2글자 이상 의미 단어 목록 (중복 없음, 순서 유지)."""
    text = re.sub(r"(?<=\d),(?=\d)", "", text or "")   # 1,450 → 1450
    text = re.sub(r"[^\w\s%]", " ", text)
    out = []
    for raw in text.split():
        for t in _forms(raw.lower()):
            if len(t) >= 2 and t not in _STOPWORDS and not t.isdigit() and t not in out:
                out.append(t)
    return out


def shared(a, b):
    return len(set(a) & set(b))


def jaccard(a, b):
    a, b = set(a), set(b)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def numbers(text):
    """'3.5%', '1,400원', '20조' 같은 숫자 표현 목록 (교차 검증용)."""
    found = []
    text = re.sub(r"(?<=\d),(?=\d)", "", text or "")
    for m in _NUM_UNIT.finditer(text):
        val = m.group(0).replace(" ", "")
        if re.search(r"\d", val) and (len(val) > 1 or val.isdigit()):
            found.append(val)
    return found
