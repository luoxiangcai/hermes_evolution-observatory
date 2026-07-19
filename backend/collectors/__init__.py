# -*- coding: utf-8 -*-
"""采集器注册表 — 管理所有采集器实例"""
from pathlib import Path
from typing import Dict, List, Optional
import logging

from .base import BaseCollector, CollectorResult
from .memory import MemoryCollector
from .skills import SkillsCollector
from .curator import CuratorCollector
from .gepa import GepaCollector
from .pending import PendingCollector
from .events import EventsCollector
from .state_db import StateDbCollector
from .checkpoints import CheckpointsCollector

logger = logging.getLogger(__name__)


class CollectorRegistry:
    """采集器注册表

    管理所有采集器实例，支持：
    - 按名称获取采集器
    - 批量执行采集
    - 注册新采集器（插件化）
    - 获取所有采集器的 Schema（用于 Drift 检测）
    """

    def __init__(self, hermes_home: Path, evolution_output_dir: Optional[Path] = None):
        self.hermes_home = hermes_home
        self.evolution_output_dir = evolution_output_dir or Path("output")
        self._collectors: Dict[str, BaseCollector] = {}
        self._register_defaults()

    def _register_defaults(self):
        """注册内置采集器"""
        self.register("memory", MemoryCollector(self.hermes_home))
        self.register("skills", SkillsCollector(self.hermes_home))
        self.register("curator", CuratorCollector(self.hermes_home))
        self.register("gepa", GepaCollector(self.hermes_home, self.evolution_output_dir))
        self.register("pending", PendingCollector(self.hermes_home))
        self.register("events", EventsCollector(self.hermes_home))
        self.register("state_db", StateDbCollector(self.hermes_home))
        self.register("checkpoints", CheckpointsCollector(self.hermes_home))

    def register(self, name: str, collector: BaseCollector):
        """注册一个采集器"""
        self._collectors[name] = collector
        logger.info(f"Registered collector: {name}")

    def get(self, name: str) -> Optional[BaseCollector]:
        """按名称获取采集器"""
        return self._collectors.get(name)

    def list_collectors(self) -> List[str]:
        """列出所有已注册的采集器名称"""
        return list(self._collectors.keys())

    def collect_all(self) -> Dict[str, CollectorResult]:
        """执行所有采集器的采集"""
        results = {}
        for name, collector in self._collectors.items():
            try:
                results[name] = collector.collect()
            except Exception as e:
                logger.error(f"Collector {name} failed: {e}")
                results[name] = CollectorResult(
                    source=name, data=None, schema_version="unknown",
                    status="error", error=str(e),
                    timestamp=__import__("datetime").datetime.utcnow().isoformat() + "Z",
                )
        return results

    def collect_one(self, name: str) -> Optional[CollectorResult]:
        """执行单个采集器的采集"""
        collector = self._collectors.get(name)
        if not collector:
            return None
        try:
            return collector.collect()
        except Exception as e:
            logger.error(f"Collector {name} failed: {e}")
            return CollectorResult(
                source=name, data=None, schema_version="unknown",
                status="error", error=str(e),
                timestamp=__import__("datetime").datetime.utcnow().isoformat() + "Z",
            )

    def get_all_schemas(self) -> list:
        """获取所有采集器的 Schema 定义"""
        return [c.get_schema() for c in self._collectors.values()]

    def get_health(self) -> list:
        """获取所有采集器的健康状态"""
        health = []
        for name, collector in self._collectors.items():
            exists = collector.check_exists()
            health.append({
                "source": name,
                "path": collector.path_pattern,
                "status": "ok" if exists else "unavailable",
                "schema_version": collector.known_schema_version,
                "exists": exists,
            })
        return health
