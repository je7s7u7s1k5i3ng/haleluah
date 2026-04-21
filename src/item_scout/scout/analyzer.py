"""경쟁강도 / 황금키워드 분석 로직."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Literal

Grade = Literal["S", "A", "B", "C", "D"]


@dataclass(slots=True)
class KeywordMetric:
    keyword: str
    total_products: int
    monthly_pc: int
    monthly_mobile: int
    comp_idx: str
    pl_avg_depth: int

    @property
    def total_qc(self) -> int:
        return self.monthly_pc + self.monthly_mobile

    @property
    def competition(self) -> float:
        """경쟁강도 = 상품수 / 총검색수. 검색수 0이면 inf."""
        if self.total_qc <= 0:
            return float("inf")
        return self.total_products / self.total_qc

    @property
    def golden_score(self) -> float:
        """황금점수 = 총검색수 / log10(상품수 + 10). 높을수록 유망."""
        return self.total_qc / math.log10(self.total_products + 10)

    @property
    def grade(self) -> Grade:
        c, v = self.competition, self.total_qc
        if c < 0.3 and v >= 1000:
            return "S"
        if c < 0.8 and v >= 500:
            return "A"
        if c < 1.5 and v >= 100:
            return "B"
        if c < 3.0:
            return "C"
        return "D"

    def to_row(self) -> dict:
        d = asdict(self)
        d.update(
            {
                "total_qc": self.total_qc,
                "competition": round(self.competition, 4),
                "golden_score": round(self.golden_score, 2),
                "grade": self.grade,
            }
        )
        return d


def filter_golden(
    metrics: list[KeywordMetric],
    *,
    min_vol: int = 500,
    max_comp: float = 1.0,
    max_products: int | None = None,
    grades: tuple[str, ...] = ("S", "A"),
) -> list[KeywordMetric]:
    out = []
    for m in metrics:
        if m.total_qc < min_vol:
            continue
        if m.competition > max_comp:
            continue
        if max_products is not None and m.total_products > max_products:
            continue
        if m.grade not in grades:
            continue
        out.append(m)
    return sorted(out, key=lambda x: x.golden_score, reverse=True)
