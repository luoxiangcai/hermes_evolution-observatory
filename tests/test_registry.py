# -*- coding: utf-8 -*-
"""测试采集器注册表"""
import pytest
from pathlib import Path
from backend.collectors import CollectorRegistry


def test_registry_init(tmp_path):
    reg = CollectorRegistry(tmp_path)
    names = reg.list_collectors()
    assert "memory" in names
    assert "skills" in names
    assert "curator" in names
    assert "events" in names
    assert "checkpoints" in names


def test_registry_collect_all(tmp_path):
    reg = CollectorRegistry(tmp_path)
    results = reg.collect_all()
    # 采集器数量随时间可能增加；只要求覆盖内置最少集合
    assert len(results) >= 8
    for name, result in results.items():
        assert result.status in ("ok", "unavailable", "error", "warning")


def test_registry_collect_one(tmp_path):
    reg = CollectorRegistry(tmp_path)
    result = reg.collect_one("memory")
    assert result is not None
    assert result.source == "memory"


def test_registry_collect_nonexistent(tmp_path):
    reg = CollectorRegistry(tmp_path)
    result = reg.collect_one("nonexistent")
    assert result is None


def test_registry_health(tmp_path):
    reg = CollectorRegistry(tmp_path)
    health = reg.get_health()
    assert len(health) >= 8
    for item in health:
        assert "source" in item
        assert "status" in item
        assert "schema_version" in item


def test_registry_schemas(tmp_path):
    reg = CollectorRegistry(tmp_path)
    schemas = reg.get_all_schemas()
    assert len(schemas) >= 8
    for s in schemas:
        assert "source" in s
        assert "version" in s


def test_checkpoints_collector_unavailable_when_no_dir(tmp_path):
    """当 skills/.checkpoints 不存在时，采集器应降级为 unavailable"""
    reg = CollectorRegistry(tmp_path)
    result = reg.collect_one("checkpoints")
    assert result is not None
    assert result.status == "unavailable"
    assert (result.data or {}).get("total_snapshots") == 0


def test_checkpoints_collector_reads_snapshots(tmp_path):
    """当有真实快照时，采集器应能正确列出"""
    import json
    from datetime import datetime
    cp_dir = tmp_path / "skills" / ".checkpoints" / "demo-skill"
    cp_dir.mkdir(parents=True)
    (cp_dir / "20260718T120000000000Z.md").write_text("# Demo v1\n\nOld content", encoding="utf-8")
    (cp_dir / "20260718T130000000000Z.md").write_text("# Demo v2\n\nNew content", encoding="utf-8")
    (cp_dir / ".meta.jsonl").write_text(
        json.dumps({"file": "20260718T120000000000Z.md", "action": "patch", "session": "sess1", "turn": 3,
                    "timestamp": "2026-07-18T12:00:00Z"}) + "\n" +
        json.dumps({"file": "20260718T130000000000Z.md", "action": "edit", "session": "sess2", "turn": 5,
                    "timestamp": "2026-07-18T13:00:00Z"}) + "\n",
        encoding="utf-8"
    )
    reg = CollectorRegistry(tmp_path)
    result = reg.collect_one("checkpoints")
    assert result.status == "ok"
    data = result.data
    assert data["total_skills"] == 1
    assert data["total_snapshots"] == 2
    snaps = data["skills"]["demo-skill"]
    assert snaps[0]["action"] == "patch"
    assert snaps[1]["action"] == "edit"
    assert snaps[0]["session"] == "sess1"
