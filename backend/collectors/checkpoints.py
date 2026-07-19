# -*- coding: utf-8 -*-
"""Checkpoints 采集器 — 读取 skills/.checkpoints/<name>/ 下的历史快照

由 evolution-observatory-hook 插件在每次 skill_manage patch/edit 前写入。
数据形态：
  skills/.checkpoints/
    <skill_name>/
      20260718T123456123456Z.md    ← 快照全文
      20260718T134012987654Z.md
      .meta.jsonl                   ← 每次写入的元数据（append-only）
"""
import json
from pathlib import Path
from datetime import datetime

from .base import BaseCollector, CollectorResult


class CheckpointsCollector(BaseCollector):
    name = "checkpoints"
    path_pattern = "skills/.checkpoints"
    known_schema_version = "v1"

    def collect(self) -> CollectorResult:
        ts = datetime.utcnow().isoformat() + "Z"
        result = CollectorResult(
            source=self.name, data={}, schema_version=self.known_schema_version, timestamp=ts
        )
        cp_root = self.hermes_home / "skills" / ".checkpoints"
        if not cp_root.exists():
            result.status = "unavailable"
            result.error = "no checkpoints directory (未启用或尚未触发过 patch/edit)"
            result.data = {"skills": {}, "total_skills": 0, "total_snapshots": 0}
            return result
        try:
            skills = {}
            total_snapshots = 0
            for skill_dir in sorted(cp_root.iterdir()):
                if not skill_dir.is_dir():
                    continue
                snapshots = []
                for f in sorted(skill_dir.iterdir()):
                    if f.suffix != ".md":
                        continue
                    try:
                        stat = f.stat()
                        snapshots.append({
                            "file": f.name,
                            "path": str(f),
                            "size": stat.st_size,
                            "mtime": datetime.utcfromtimestamp(stat.st_mtime).isoformat() + "Z",
                        })
                    except Exception:
                        pass
                # 合并 metadata（若有）
                meta_file = skill_dir / ".meta.jsonl"
                meta_by_file = {}
                if meta_file.exists():
                    try:
                        for line in meta_file.read_text(encoding="utf-8", errors="replace").splitlines():
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                m = json.loads(line)
                                if m.get("file"):
                                    meta_by_file[m["file"]] = m
                            except Exception:
                                pass
                    except Exception:
                        pass
                for s in snapshots:
                    m = meta_by_file.get(s["file"])
                    if m:
                        s["action"] = m.get("action")
                        s["session"] = m.get("session")
                        s["turn"] = m.get("turn")
                        s["timestamp"] = m.get("timestamp") or s["mtime"]
                    else:
                        s["timestamp"] = s["mtime"]
                skills[skill_dir.name] = snapshots
                total_snapshots += len(snapshots)
            result.data = {
                "skills": skills,
                "total_skills": len(skills),
                "total_snapshots": total_snapshots,
            }
        except Exception as e:
            result.status = "error"
            result.error = str(e)
        return result
