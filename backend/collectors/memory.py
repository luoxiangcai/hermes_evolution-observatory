# -*- coding: utf-8 -*-
"""MEMORY.md / USER.md 采集器"""
from pathlib import Path
from datetime import datetime
import re

from .base import BaseCollector, CollectorResult


class MemoryCollector(BaseCollector):
    name = "memory"
    path_pattern = "memories/MEMORY.md"
    known_schema_version = "v1"

    def collect(self) -> CollectorResult:
        ts = datetime.utcnow().isoformat() + "Z"
        result = CollectorResult(
            source=self.name, data={}, schema_version=self.known_schema_version, timestamp=ts
        )

        memory_data = self._read_memory_file("MEMORY.md", 2200)
        user_data = self._read_memory_file("USER.md", 1375)

        if memory_data["status"] == "unavailable" and user_data["status"] == "unavailable":
            result.status = "unavailable"
            result.error = "Neither MEMORY.md nor USER.md found"
            return result

        result.data = {"memory": memory_data, "user": user_data}
        if memory_data["status"] == "error" or user_data["status"] == "error":
            result.status = "warning"
        return result

    def _read_memory_file(self, filename: str, char_limit: int) -> dict:
        path = self.hermes_home / "memories" / filename
        abs_path = str(path.resolve())
        if not path.exists():
            return {"status": "unavailable", "entries": [], "usage": 0, "limit": char_limit, "abs_path": abs_path}

        try:
            content = path.read_text(encoding="utf-8")
            # 解析 § 分隔的条目
            entries = self._parse_entries(content)
            usage = len(content)
            return {
                "status": "ok",
                "entries": entries,
                "raw_content": content,
                "usage": usage,
                "limit": char_limit,
                "usage_percent": round(usage / char_limit * 100, 1) if char_limit > 0 else 0,
                "abs_path": abs_path,
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "entries": [], "usage": 0, "limit": char_limit, "abs_path": abs_path}

    def _parse_entries(self, content: str) -> list:
        """解析 § 分隔的记忆条目"""
        # 移除头部（═══ 包围的标题行）
        lines = content.strip().split("\n")
        entries = []
        current_entry = []
        in_entry = False

        for line in lines:
            if line.strip().startswith("§"):
                if current_entry:
                    entries.append("\n".join(current_entry).strip())
                current_entry = []
                in_entry = True
            elif in_entry:
                current_entry.append(line)

        if current_entry:
            entries.append("\n".join(current_entry).strip())

        return [e for e in entries if e]
