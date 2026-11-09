"""SQLite 기록: 회차별 단어 보도량(급상승 비교용), 이미 본 기사·영상(재시작 후에도 중복 방지)"""

import sqlite3
from datetime import datetime, timedelta


class Store:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(str(db_path))
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS token_counts (
                day TEXT, category TEXT, token TEXT, n INTEGER,
                PRIMARY KEY (day, category, token)
            );
            CREATE TABLE IF NOT EXISTS seen (
                kind TEXT, key TEXT, first_seen TEXT,
                PRIMARY KEY (kind, key)
            );
            """
        )

    def save_token_counts(self, day, category, counts):
        self.conn.executemany(
            "INSERT OR REPLACE INTO token_counts VALUES (?, ?, ?, ?)",
            [(day, category, t, n) for t, n in counts.items()],
        )
        self.conn.commit()

    def baseline(self, day, category, token, days=7):
        """오늘을 뺀 지난 N일 하루 평균 보도량. 기록이 없으면 None."""
        start = (datetime.strptime(day, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = self.conn.execute(
            "SELECT n FROM token_counts WHERE category=? AND token=? AND day>=? AND day<?",
            (category, token, start, day),
        ).fetchall()
        recorded_days = self.conn.execute(
            "SELECT COUNT(DISTINCT day) FROM token_counts WHERE category=? AND day>=? AND day<?",
            (category, start, day),
        ).fetchone()[0]
        if recorded_days == 0:
            return None
        return sum(r[0] for r in rows) / recorded_days

    def mark_seen(self, kind, key):
        """처음 보는 것이면 True."""
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO seen VALUES (?, ?, ?)",
            (kind, key, datetime.now().isoformat(timespec="seconds")),
        )
        self.conn.commit()
        return cur.rowcount == 1

    def close(self):
        self.conn.close()
