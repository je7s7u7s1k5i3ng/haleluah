from item_scout.scout.analyzer import KeywordMetric, filter_golden


def _m(keyword, products, pc, mobile):
    return KeywordMetric(
        keyword=keyword,
        total_products=products,
        monthly_pc=pc,
        monthly_mobile=mobile,
        comp_idx="중간",
        pl_avg_depth=10,
    )


def test_total_qc():
    assert _m("a", 100, 300, 700).total_qc == 1000


def test_competition_zero_vol_is_inf():
    assert _m("a", 100, 0, 0).competition == float("inf")


def test_competition_ratio():
    assert _m("a", 500, 200, 800).competition == 0.5


def test_grade_s():
    m = _m("a", 200, 500, 1500)  # comp=0.1, vol=2000
    assert m.grade == "S"


def test_grade_a():
    m = _m("a", 500, 300, 500)  # comp=0.625, vol=800
    assert m.grade == "A"


def test_grade_b():
    m = _m("a", 400, 100, 200)  # comp=1.333, vol=300
    assert m.grade == "B"


def test_grade_d_for_high_comp():
    m = _m("a", 10000, 100, 100)  # comp=50
    assert m.grade == "D"


def test_golden_score_prefers_high_vol_low_products():
    hi_vol_low_prod = _m("x", 100, 500, 2500)
    lo_vol_hi_prod = _m("y", 50000, 50, 450)
    assert hi_vol_low_prod.golden_score > lo_vol_hi_prod.golden_score


def test_filter_golden_sorts_and_filters():
    ms = [
        _m("best", 100, 500, 2500),   # comp ~0.033, S
        _m("meh", 50000, 100, 400),   # comp 100, D
        _m("ok", 400, 300, 700),      # comp 0.4, A
        _m("lowvol", 10, 10, 10),     # vol 20
    ]
    gold = filter_golden(ms, min_vol=500, max_comp=1.0)
    assert [g.keyword for g in gold] == ["best", "ok"]
