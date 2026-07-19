# -*- coding: utf-8 -*-
"""state.db 采集器 — SQLite + FTS5 会话检索"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime

from .base import BaseCollector, CollectorResult


class StateDbCollector(BaseCollector):
    name = "state_db"
    path_pattern = "state.db"
    known_schema_version = "FTS5/v1"

    def collect(self) -> CollectorResult:
        ts = datetime.utcnow().isoformat() + "Z"
        result = CollectorResult(
            source=self.name, data={}, schema_version=self.known_schema_version, timestamp=ts
        )

        db_path = self.hermes_home / "state.db"
        if not db_path.exists():
            result.status = "unavailable"
            result.error = "state.db not found"
            return result

        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row

            # 获取会话统计
            session_stats = self._get_session_stats(conn)
            # 获取最近的进化相关会话
            recent_sessions = self._get_recent_sessions(conn, limit=20)

            conn.close()

            result.data = {
                "session_stats": session_stats,
                "recent_sessions": recent_sessions,
            }
        except Exception as e:
            result.status = "error"
            result.error = str(e)
        return result

    def _get_session_stats(self, conn) -> dict:
        try:
            cursor = conn.execute("SELECT COUNT(*) as count FROM sessions")
            total = cursor.fetchone()["count"]
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM sessions WHERE created_at > datetime('now', '-7 days')"
            )
            recent = cursor.fetchone()["count"]
            return {"total_sessions": total, "recent_7d": recent}
        except Exception:
            return {"total_sessions": 0, "recent_7d": 0, "error": "query failed"}

    def _get_recent_sessions(self, conn, limit: int = 20) -> list:
        try:
            cursor = conn.execute(
                "SELECT id, title, source, created_at FROM sessions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    def search(self, query: str, limit: int = 10) -> list:
        """FTS5 全文检索"""
        db_path = self.hermes_home / "state.db"
        if not db_path.exists():
            return []

        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT session_id, snippet(messages_fts, -1, '>>>', '<<<', '...', 10) as snippet "
                "FROM messages_fts WHERE messages_fts MATCH ? LIMIT ?",
                (query, limit),
            )
            results = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return results
        except Exception:
            return []
