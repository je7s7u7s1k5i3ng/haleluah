"""SQLite 스냅샷 저장소."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from ..scout.analyzer import KeywordMetric

SCHEMA = """
CREATE TABLE IF NOT EXISTS keyword_snapshot (
    keyword         TEXT    NOT NULL,
    captured_at     TEXT    NOT NULL,
    total_products  INTEGER NOT NULL,
    monthly_pc      INTEGER NOT NULL,
    monthly_mobile  INTEGER NOT NULL,
    comp_idx        TEXT,
    pl_avg_depth    INTEGER,
    competition     REAL,
    golden_score    REAL,
    grade           TEXT,
    PRIMARY KEY (keyword, captured_at)
);
CREATE INDEX IF NOT EXISTS idx_snapshot_keyword ON keyword_snapshot(keyword);
CREATE INDEX IF NOT EXISTS idx_snapshot_captured ON keyword_snapshot(captured_at);

CREATE TABLE IF NOT EXISTS rank_track (
    product_id  TEXT NOT NULL,
    keyword     TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    rank        INTEGER,
    PRIMARY KEY (product_id, keyword, captured_at)
);

CREATE TABLE IF NOT EXISTS api_quota (
    day       TEXT NOT NULL,
    api       TEXT NOT NULL,
    calls     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, api)
);
"""


class Storage:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def save_metrics(self, metrics: list[KeywordMetric]) -> None:
        if not metrics:
            return
        now = datetime.utcnow().isoformat(timespec="seconds")
        rows = [
            (
                m.keyword,
                now,
                m.total_products,
                m.monthly_pc,
                m.monthly_mobile,
                m.comp_idx,
                m.pl_avg_depth,
                None if m.competition == float("inf") else m.competition,
                m.golden_score,
                m.grade,
            )
            for m in metrics
        ]
        with self._conn() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executemany(
                "INSERT OR REPLACE INTO keyword_snapshot VALUES (?,?,?,?,?,?,?,?,?,?)",
                rows,
            )

    def query_golden(
        self,
        *,
        min_vol: int = 500,
        max_comp: float = 1.0,
        limit: int = 500,
    ) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                """SELECT * FROM keyword_snapshot
                   WHERE (monthly_pc + monthly_mobile) >= ?
                     AND competition IS NOT NULL AND competition <= ?
                   ORDER BY golden_score DESC, captured_at DESC
                   LIMIT ?""",
                (min_vol, max_comp, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def fresh_keyword(self, keyword: str, ttl_hours: int) -> dict | None:
        cutoff = (datetime.utcnow() - timedelta(hours=ttl_hours)).isoformat(
            timespec="seconds"
        )
        with self._conn() as c:
            row = c.execute(
                """SELECT * FROM keyword_snapshot
                   WHERE keyword = ? AND captured_at >= ?
                   ORDER BY captured_at DESC LIMIT 1""",
                (keyword, cutoff),
            ).fetchone()
        return dict(row) if row else None

    def save_rank(self, product_id: str, keyword: str, rank: int | None) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO rank_track VALUES (?,?,?,?)",
                (product_id, keyword, now, rank),
            )

    def bump_quota(self, api: str, calls: int = 1) -> None:
        day = datetime.utcnow().date().isoformat()
        with self._conn() as c:
            c.execute(
                """INSERT INTO api_quota(day, api, calls) VALUES(?, ?, ?)
                   ON CONFLICT(day, api) DO UPDATE SET calls = calls + excluded.calls""",
                (day, api, calls),
            )

    def quota_today(self) -> dict[str, int]:
        day = datetime.utcnow().date().isoformat()
        with self._conn() as c:
            rows = c.execute(
                "SELECT api, calls FROM api_quota WHERE day = ?", (day,)
            ).fetchall()
        return {r["api"]: r["calls"] for r in rows}

    def query_keywords(
        self,
        *,
        min_vol: int | None = None,
        max_vol: int | None = None,
        min_comp: float | None = None,
        max_comp: float | None = None,
        grades: list[str] | None = None,
        contains: str | None = None,
        order_by: str = "golden_score",
        limit: int = 100,
    ) -> list[dict]:
        """유연한 DB 조회 (Claude가 쓰기 좋은 형태)."""
        wh: list[str] = ["1=1"]
        params: list = []
        if min_vol is not None:
            wh.append("(monthly_pc + monthly_mobile) >= ?"); params.append(min_vol)
        if max_vol is not None:
            wh.append("(monthly_pc + monthly_mobile) <= ?"); params.append(max_vol)
        if min_comp is not None:
            wh.append("competition >= ?"); params.append(min_comp)
        if max_comp is not None:
            wh.append("competition IS NOT NULL AND competition <= ?"); params.append(max_comp)
        if grades:
            ph = ",".join("?" for _ in grades)
            wh.append(f"grade IN ({ph})"); params.extend(grades)
        if contains:
            wh.append("keyword LIKE ?"); params.append(f"%{contains}%")

        allowed = {"golden_score", "competition", "total_products", "captured_at"}
        ob = order_by if order_by in allowed else "golden_score"
        direction = "ASC" if ob == "competition" else "DESC"

        sql = f"""
            SELECT keyword, total_products, monthly_pc, monthly_mobile,
                   (monthly_pc + monthly_mobile) AS total_qc,
                   competition, golden_score, grade, comp_idx, captured_at
            FROM keyword_snapshot
            WHERE {" AND ".join(wh)}
            ORDER BY {ob} {direction}
            LIMIT ?
        """
        params.append(limit)
        with self._conn() as c:
            rows = c.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def summary(self) -> dict:
        with self._conn() as c:
            row = c.execute(
                """SELECT COUNT(*) AS total,
                          SUM(CASE WHEN grade='S' THEN 1 ELSE 0 END) AS s_cnt,
                          SUM(CASE WHEN grade='A' THEN 1 ELSE 0 END) AS a_cnt,
                          SUM(CASE WHEN grade='B' THEN 1 ELSE 0 END) AS b_cnt,
                          MIN(captured_at) AS first_at,
                          MAX(captured_at) AS last_at
                   FROM keyword_snapshot"""
            ).fetchone()
        return dict(row) if row else {}

    def seed_coverage(self, seeds: list[str], ttl_hours: int) -> dict[str, bool]:
        """시드 목록 중 최근 수집된 것 여부. Claude가 중복 시드 피하는 용도."""
        cutoff = (datetime.utcnow() - timedelta(hours=ttl_hours)).isoformat(timespec="seconds")
        out: dict[str, bool] = {}
        with self._conn() as c:
            for s in seeds:
                row = c.execute(
                    "SELECT 1 FROM keyword_snapshot WHERE keyword=? AND captured_at>=? LIMIT 1",
                    (s, cutoff),
                ).fetchone()
                out[s] = row is not None
        return out
