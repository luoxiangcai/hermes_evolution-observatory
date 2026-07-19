# -*- coding: utf-8 -*-
"""进化叙事生成器 — 从事件流自动生成故事线"""
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class NarrativeGenerator:
    """进化叙事生成器

    从 evolution-events.jsonl 读取事件，按时间/层次/Profile 组织，
    生成人类可读的"进化故事线"。
    """

    # 事件类型到中文描述的映射
    TYPE_LABELS = {
        "memory": "记忆更新",
        "skill": "技能进化",
        "curator": "Curator 维护",
        "gepa": "GEPA 优化",
        "session": "会话活动",
    }

    # 触发源到中文描述的映射
    ORIGIN_LABELS = {
        "background_review fork": "后台反思",
        "foreground turn": "前台对话",
        "self-evolution pipeline": "离线优化管道",
        "Curator (idle check)": "Curator 空闲检查",
    }

    def __init__(self, hermes_home: Path):
        self.hermes_home = hermes_home
        self.events_file = hermes_home / "logs" / "evolution-events.jsonl"

    def generate(self, profile: str = "default", days: int = 7) -> dict:
        """生成进化叙事

        Args:
            profile: Profile 名称
            days: 回溯天数

        Returns:
            {
                "title": "进化故事线",
                "period": "2026-07-09 ~ 2026-07-16",
                "profile": "default",
                "summary": "本周共发生 23 次进化事件...",
                "chapters": [...],
                "stats": {...}
            }
        """
        events = self._load_events(profile, days)
        if not events:
            return {
                "title": "进化故事线",
                "profile": profile,
                "summary": "暂无进化事件记录。",
                "chapters": [],
                "stats": {"total_events": 0},
            }

        # 按日期分组
        by_date = self._group_by_date(events)
        # 按类型统计
        by_type = self._count_by_type(events)
        # 按层次统计
        by_layer = self._count_by_layer(events)

        # 生成章节
        chapters = []
        for date, date_events in sorted(by_date.items(), reverse=True):
            chapter = self._build_chapter(date, date_events)
            chapters.append(chapter)

        # 生成摘要
        summary = self._build_summary(events, by_type, by_layer, days)

        return {
            "title": "进化故事线",
            "profile": profile,
            "period": f"{chapters[-1]['date']} ~ {chapters[0]['date']}" if chapters else "",
            "summary": summary,
            "chapters": chapters,
            "stats": {
                "total_events": len(events),
                "by_type": by_type,
                "by_layer": by_layer,
                "days_covered": len(by_date),
            },
        }

    def generate_markdown(self, profile: str = "default", days: int = 7) -> str:
        """生成 Markdown 格式的进化叙事"""
        narrative = self.generate(profile, days)

        lines = [
            f"# {narrative['title']}",
            "",
            f"> Profile: {narrative['profile']} | 时间范围: {narrative.get('period', 'N/A')}",
            "",
            f"## 摘要",
            "",
            narrative["summary"],
            "",
            f"## 统计",
            "",
            f"- 总事件数: {narrative['stats']['total_events']}",
            f"- 覆盖天数: {narrative['stats']['days_covered']}",
        ]

        if narrative["stats"].get("by_type"):
            lines.append("")
            lines.append("### 按类型分布")
            for t, c in narrative["stats"]["by_type"].items():
                label = self.TYPE_LABELS.get(t, t)
                lines.append(f"- {label}: {c}")

        if narrative["stats"].get("by_layer"):
            lines.append("")
            lines.append("### 按进化层次分布")
            for l, c in narrative["stats"]["by_layer"].items():
                lines.append(f"- {l}: {c}")

        lines.append("")
        lines.append("## 详细时间线")
        for chapter in narrative["chapters"]:
            lines.append("")
            lines.append(f"### {chapter['date']}")
            lines.append("")
            for event in chapter["events"]:
                lines.append(f"- **{event['time']}** {event['description']}")

        return "\n".join(lines)

    def _load_events(self, profile: str, days: int) -> list:
        if not self.events_file.exists():
            return []

        # events 文件本身已经按 profile 隔离在 <hermes_home>/logs/ 下，不再二次过滤
        events = []
        for line in self.events_file.read_text(encoding="utf-8").strip().split("\n"):
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        # 时间过滤
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        cutoff_iso = cutoff.isoformat()
        events = [e for e in events if e.get("timestamp", "9999") >= cutoff_iso]

        # 按时间倒序
        events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        return events

    def _group_by_date(self, events: list) -> dict:
        grouped = defaultdict(list)
        for event in events:
            ts = event.get("timestamp", "")
            date = ts[:10] if len(ts) >= 10 else "unknown"
            grouped[date].append(event)
        return dict(grouped)

    def _count_by_type(self, events: list) -> dict:
        counts = defaultdict(int)
        for event in events:
            counts[event.get("type", "unknown")] += 1
        return dict(counts)

    def _count_by_layer(self, events: list) -> dict:
        counts = defaultdict(int)
        for event in events:
            origin = event.get("origin", "")
            if "background" in origin:
                counts["L1 运行时"] += 1
            elif "self-evolution" in origin or "gepa" in str(event.get("type", "")):
                counts["L3 系统级"] += 1
            elif "curator" in origin or event.get("type") == "curator":
                counts["L2 沉淀"] += 1
            else:
                counts["其他"] += 1
        return dict(counts)

    def _build_chapter(self, date: str, events: list) -> dict:
        chapter_events = []
        for event in events:
            ts = event.get("timestamp", "")
            time_str = ts[11:19] if len(ts) >= 19 else ""

            event_type = event.get("type", "unknown")
            desc = event.get("desc", event.get("description", ""))
            origin = event.get("origin", "")

            chapter_events.append({
                "time": time_str,
                "type": event_type,
                "type_label": self.TYPE_LABELS.get(event_type, event_type),
                "description": desc,
                "origin": origin,
                "origin_label": self.ORIGIN_LABELS.get(origin, origin),
                "session_id": event.get("session", ""),
                "turn": event.get("turn", 0),
            })

        return {"date": date, "events": chapter_events, "count": len(chapter_events)}

    def _build_summary(self, events: list, by_type: dict, by_layer: dict, days: int) -> str:
        total = len(events)
        type_parts = []
        for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
            label = self.TYPE_LABELS.get(t, t)
            type_parts.append(f"{label} {c} 次")

        layer_parts = []
        for l, c in sorted(by_layer.items(), key=lambda x: -x[1]):
            layer_parts.append(f"{l} {c} 次")

        return (
            f"过去 {days} 天内共发生 {total} 次进化事件"
            f"（{'，'.join(type_parts)}）。"
            f"按进化层次分布：{'，'.join(layer_parts)}。"
        )
