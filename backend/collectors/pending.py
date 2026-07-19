# -*- coding: utf-8 -*-
"""待审批写入采集器 — pending/memory/ + pending/skills/"""
import json
from pathlib import Path
from datetime import datetime

from .base import BaseCollector, CollectorResult


class PendingCollector(BaseCollector):
    name = "pending"
    path_pattern = "pending"
    known_schema_version = "v1"

    def collect(self) -> CollectorResult:
        ts = datetime.utcnow().isoformat() + "Z"
        result = CollectorResult(
            source=self.name, data={}, schema_version=self.known_schema_version, timestamp=ts
        )

        pending_dir = self.hermes_home / "pending"
        if not pending_dir.exists():
            result.data = {"memory": [], "skills": [], "total": 0}
            return result

        try:
            memory_pending = self._scan_dir(pending_dir / "memory")
            skills_pending = self._scan_dir(pending_dir / "skills")

            result.data = {
                "memory": memory_pending,
                "skills": skills_pending,
                "total": len(memory_pending) + len(skills_pending),
            }
        except Exception as e:
            result.status = "error"
            result.error = str(e)
        return result

    def _scan_dir(self, dir_path: Path) -> list:
        if not dir_path.exists():
            return []
        items = []
        for f in dir_path.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                data["filename"] = f.name
                items.append(data)
            except Exception:
                items.append({"filename": f.name, "error": "failed to parse"})
        return items
