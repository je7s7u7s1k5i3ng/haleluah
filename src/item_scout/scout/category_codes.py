"""네이버 쇼핑 주요 카테고리 코드 (DataLab 용)."""

CATEGORIES: dict[str, str] = {
    "패션의류": "50000000",
    "패션잡화": "50000001",
    "화장품미용": "50000002",
    "디지털가전": "50000003",
    "가구인테리어": "50000004",
    "출산육아": "50000005",
    "식품": "50000006",
    "스포츠레저": "50000007",
    "생활건강": "50000008",
    "여가생활편의": "50000009",
    "면세점": "50000010",
}


def resolve(name_or_code: str) -> str:
    if name_or_code.isdigit():
        return name_or_code
    if name_or_code in CATEGORIES:
        return CATEGORIES[name_or_code]
    raise ValueError(
        f"알 수 없는 카테고리: {name_or_code}. "
        f"지원 카테고리: {', '.join(CATEGORIES)}"
    )
