import orjson
import pytest

from item_scout.scout.analyzer import KeywordMetric
from item_scout.storage.db import Storage


def _m(k, prod, pc, mo):
    return KeywordMetric(
        keyword=k,
        total_products=prod,
        monthly_pc=pc,
        monthly_mobile=mo,
        comp_idx="중간",
        pl_avg_depth=10,
    )


def test_bump_and_read_quota(tmp_path):
    st = Storage(tmp_path / "q.db")
    st.bump_quota("shopping", 10)
    st.bump_quota("shopping", 5)
    st.bump_quota("searchad", 3)
    today = st.quota_today()
    assert today["shopping"] == 15
    assert today["searchad"] == 3


def test_query_keywords_filters_and_orders(tmp_path):
    st = Storage(tmp_path / "q.db")
    st.save_metrics([
        _m("무선이어폰", 5000, 300, 700),    # comp 5.0 (D)
        _m("수면양말", 200, 500, 1500),      # comp 0.1 (S)
        _m("캠핑의자", 800, 300, 700),       # comp 0.8 (A)
    ])
    rows = st.query_keywords(max_comp=1.0, limit=10)
    kws = [r["keyword"] for r in rows]
    assert "수면양말" in kws
    assert "캠핑의자" in kws
    assert "무선이어폰" not in kws

    rows2 = st.query_keywords(grades=["S"], limit=10)
    assert [r["keyword"] for r in rows2] == ["수면양말"]

    rows3 = st.query_keywords(contains="캠핑", limit=10)
    assert [r["keyword"] for r in rows3] == ["캠핑의자"]


def test_summary_counts_grades(tmp_path):
    st = Storage(tmp_path / "s.db")
    st.save_metrics([
        _m("a", 200, 500, 1500),   # comp 0.1 vol 2000 → S
        _m("b", 500, 300, 500),    # comp 0.625 vol 800 → A
        _m("c", 400, 100, 200),    # comp 1.333 vol 300 → B
        _m("d", 20000, 50, 50),    # comp 200 → D
    ])
    s = st.summary()
    assert s["total"] == 4
    assert s["s_cnt"] == 1
    assert s["a_cnt"] == 1
    assert s["b_cnt"] == 1


def test_seed_coverage(tmp_path):
    st = Storage(tmp_path / "c.db")
    st.save_metrics([_m("캠핑", 100, 100, 100)])
    cov = st.seed_coverage(["캠핑", "수면양말"], ttl_hours=24)
    assert cov["캠핑"] is True
    assert cov["수면양말"] is False
