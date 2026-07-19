# -*- coding: utf-8 -*-
"""测试降级模式 — 数据源不存在时不应崩溃"""
import pytest
from pathlib import Path
from backend.collectors import CollectorRegistry
from backend.collectors.memory import MemoryCollector
from backend.collectors.skills import SkillsCollector
from backend.collectors.events import EventsCollector


def test_memory_collector_empty_home(tmp_path):
    """空目录下 MemoryCollector 应返回 unavailable"""
    c = MemoryCollector(tmp_path)
    result = c.collect()
    assert result.status == "unavailable"


def test_skills_collector_empty_home(tmp_path):
    """空目录下 SkillsCollector 应返回 unavailable"""
    c = SkillsCollector(tmp_path)
    result = c.collect()
    assert result.status == "unavailable"


def test_events_collector_empty_home(tmp_path):
    """空目录下 EventsCollector 应返回空列表"""
    c = EventsCollector(tmp_path)
    result = c.collect()
    assert result.status == "ok"
    assert result.data["events"] == []
    assert result.data["total"] == 0


def test_registry_degraded_mode(tmp_path):
    """所有数据源都不存在时，collect_all 不应抛异常"""
    reg = CollectorRegistry(tmp_path)
    results = reg.collect_all()
    for name, result in results.items():
        assert result.status in ("ok", "unavailable", "error", "warning")
        assert result.source == name


def test_memory_collector_with_data(tmp_path):
    """有数据时 MemoryCollector 应正确解析"""
    memories_dir = tmp_path / "memories"
    memories_dir.mkdir()
    (memories_dir / "MEMORY.md").write_text(
        "══════════════════════════════════════════════\n"
        "MEMORY [50% — 1,100/2,200 chars]\n"
        "══════════════════════════════════════════════\n"
        "§\n"
        "User runs macOS 14 Sonoma, uses Homebrew.\n"
        "§\n"
        "Project ~/code/api uses Go 1.22.\n",
        encoding="utf-8",
    )
    c = MemoryCollector(tmp_path)
    result = c.collect()
    assert result.status == "ok"
    assert len(result.data["memory"]["entries"]) == 2
    assert result.data["memory"]["usage"] > 0
