# -*- coding: utf-8 -*-
"""测试采集器基类"""
import pytest
from pathlib import Path
from backend.collectors.base import BaseCollector, CollectorResult


class TestCollector(BaseCollector):
    name = "test"
    path_pattern = "test_file.txt"
    known_schema_version = "v1"

    def collect(self) -> CollectorResult:
        path = self.hermes_home / self.path_pattern
        if not path.exists():
            return CollectorResult(
                source=self.name, data=None, schema_version=self.known_schema_version,
                status="unavailable", error="file not found",
                timestamp="2026-01-01T00:00:00Z",
            )
        return CollectorResult(
            source=self.name, data=path.read_text(),
            schema_version=self.known_schema_version, status="ok",
            timestamp="2026-01-01T00:00:00Z",
        )


def test_collector_exists(tmp_path):
    c = TestCollector(tmp_path)
    assert c.check_exists() is False
    (tmp_path / "test_file.txt").write_text("hello")
    assert c.check_exists() is True


def test_collector_unavailable(tmp_path):
    c = TestCollector(tmp_path)
    result = c.collect()
    assert result.status == "unavailable"
    assert result.error is not None


def test_collector_ok(tmp_path):
    (tmp_path / "test_file.txt").write_text("hello")
    c = TestCollector(tmp_path)
    result = c.collect()
    assert result.status == "ok"
    assert result.data == "hello"


def test_collector_schema():
    c = TestCollector(Path("/tmp"))
    schema = c.get_schema()
    assert schema["source"] == "test"
    assert schema["version"] == "v1"
