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
            c.executemany(
                "INSERT OR REPLACE INTO keyword_snapshot VALUES (?,?,?,?,?,?,?,?,?,?)",
                rows,
            )

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
