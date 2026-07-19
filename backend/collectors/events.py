# -*- coding: utf-8 -*-
"""进化事件采集器 — 读取 evolution-events.jsonl

支持三种事件源：
  1. 当前 profile 的 <hermes_home>/logs/evolution-events.jsonl
  2. 所有兄弟 profile 的 logs/evolution-events.jsonl（用于跨 profile 混排视图）
  3. hermes root 的 logs/evolution-events.jsonl（default profile）

如 all_profiles=True，采集器会合并所有源并按时间倒序返回。
"""
import json
from pathlib import Path
from datetime import datetime

from .base import BaseCollector, CollectorResult


class EventsCollector(BaseCollector):
    name = "events"
    path_pattern = "logs/evolution-events.jsonl"
    known_schema_version = "v1"

    # 是否跨 profile 混排（前端可通过 /api/timeline?all_profiles=true 触发）
    def collect(self, all_profiles: bool = False) -> CollectorResult:
        ts = datetime.utcnow().isoformat() + "Z"
        result = CollectorResult(
            source=self.name, data={}, schema_version=self.known_schema_version, timestamp=ts
        )

        files = self._enumerate_event_files(all_profiles=all_profiles)
        if not files:
            result.data = {"events": [], "total": 0, "sources": []}
            return result

        try:
            events = []
            sources = []
            for pf_name, fp in files:
                exists = fp.exists()
                sources.append({
                    "profile": pf_name,
                    "file": str(fp),
                    "exists": exists,
                    "size": fp.stat().st_size if exists else 0,
                })
                if not exists:
                    continue
                for line in fp.read_text(encoding="utf-8").strip().split("\n"):
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                        ev.setdefault("profile", pf_name)
                        events.append(ev)
                    except json.JSONDecodeError:
                        continue

            events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
            result.data = {"events": events, "total": len(events), "sources": sources}
        except Exception as e:
            result.status = "error"
            result.error = str(e)
        return result

    def _enumerate_event_files(self, all_profiles: bool = False):
        """列出所有 (profile_name, path) 对。
        - all_profiles=False：只当前 hermes_home
        - all_profiles=True：hermes root + 所有 profiles/<name>/
        """
        out = []
        hh = self.hermes_home

        if not all_profiles:
            # 单 profile 模式：hh 就是要读的
            pf = self._infer_profile_name(hh)
            out.append((pf, hh / "logs" / "evolution-events.jsonl"))
            return out

        # 跨 profile 模式：找 hermes root
        # hh 可能是 ~/.hermes（default）也可能是 ~/.hermes/profiles/<name>
        if hh.parent.name == "profiles":
            root = hh.parent.parent  # ~/.hermes
        else:
            root = hh
        # default = 根目录
        out.append(("default", root / "logs" / "evolution-events.jsonl"))
        # 其他 profiles
        profiles_dir = root / "profiles"
        if profiles_dir.exists():
            for pf_dir in sorted(profiles_dir.iterdir()):
                if pf_dir.is_dir():
                    out.append((pf_dir.name, pf_dir / "logs" / "evolution-events.jsonl"))
        return out

    def _infer_profile_name(self, hh: Path) -> str:
        if hh.parent.name == "profiles":
            return hh.name
        return "default"

    def append_event(self, event: dict) -> bool:
        """追加一条进化事件到 jsonl 文件（供 Plugin Hook 调用；写入本 profile）"""
        events_file = self.hermes_home / "logs" / "evolution-events.jsonl"
        try:
            events_file.parent.mkdir(parents=True, exist_ok=True)
            with open(events_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
            return True
        except Exception:
            return False
