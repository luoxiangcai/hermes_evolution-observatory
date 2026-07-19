# -*- coding: utf-8 -*-
"""Schema 注册表 + Drift 检测引擎"""
import json
import os
import socket
import time
import httpx
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger(__name__)


# 全局端口探测缓存：{(host,port): (is_open, expire_ts)}
_PORT_CACHE: dict = {}
_PORT_CACHE_TTL = 30  # 秒


def _is_port_open(host: str, port: int, timeout: float = 0.15) -> bool:
    """快速探测 TCP 端口是否可连，30s 内结果缓存"""
    key = (host, port)
    now = time.time()
    cached = _PORT_CACHE.get(key)
    if cached and cached[1] > now:
        return cached[0]
    try:
        with socket.create_connection((host, port), timeout=timeout):
            _PORT_CACHE[key] = (True, now + _PORT_CACHE_TTL)
            return True
    except Exception:
        _PORT_CACHE[key] = (False, now + _PORT_CACHE_TTL)
        return False


@dataclass
class DriftResult:
    """Drift 检测结果"""
    severity: str  # info / warning / error
    title: str
    description: str
    source: str
    detected_at: str
    impact: str = ""


class SchemaRegistry:
    """Schema 注册表

    维护观测台已知的所有数据源 Schema。
    检测到未知 Schema 时告警，不崩溃。
    """

    # 已知的 Hermes 配置 Schema 版本
    KNOWN_CONFIG_VERSIONS = {16, 17}

    # 已知的 skill_manage actions
    KNOWN_SKILL_ACTIONS = {"create", "patch", "edit", "delete", "write_file", "remove_file"}

    # 已知的 memory actions
    KNOWN_MEMORY_ACTIONS = {"add", "replace", "remove"}

    # 已知的事件类型
    KNOWN_EVENT_TYPES = {"memory", "skill", "curator", "gepa", "session"}

    def __init__(self, hermes_home: Path, dashboard_url: str = "http://127.0.0.1:9119"):
        self.hermes_home = hermes_home
        self.dashboard_url = dashboard_url
        self.last_hermes_version: Optional[str] = None
        self.last_config_schema: Optional[dict] = None
        self._drift_log_file = hermes_home / "logs" / "observatory-drift.jsonl"

    def _dashboard_probe(self) -> bool:
        """快速探测 dashboard 端口，未起时后续 http 检查全部跳过"""
        try:
            from urllib.parse import urlparse
            u = urlparse(self.dashboard_url)
            return _is_port_open(u.hostname or "127.0.0.1", u.port or 9119, timeout=0.15)
        except Exception:
            return False

    def check_version(self) -> Optional[DriftResult]:
        """第 1 层：版本探测"""
        if not self._dashboard_probe():
            return None
        try:
            resp = httpx.get(f"{self.dashboard_url}/api/status", timeout=httpx.Timeout(1.0, connect=0.5))
            if resp.status_code != 200:
                return None
            data = resp.json()
            current_version = data.get("version", "unknown")

            if self.last_hermes_version and self.last_hermes_version != current_version:
                return DriftResult(
                    severity="info",
                    title="Hermes 版本变化",
                    description=f"Hermes 版本从 {self.last_hermes_version} 变为 {current_version}",
                    source="/api/status",
                    detected_at=datetime.utcnow().isoformat() + "Z",
                    impact="低 — 观测台将自动重新检测所有数据源",
                )
            self.last_hermes_version = current_version
        except Exception as e:
            logger.debug(f"Version check failed (dashboard may be offline): {e}")
        return None

    def check_config_schema(self) -> Optional[DriftResult]:
        """第 2 层：配置 Schema 探测"""
        if not self._dashboard_probe():
            return None
        try:
            resp = httpx.get(f"{self.dashboard_url}/api/config/schema", timeout=httpx.Timeout(1.0, connect=0.5))
            if resp.status_code != 200:
                return None
            current_schema = resp.json()

            if self.last_config_schema:
                # 对比新增的配置项
                old_keys = set(self._extract_keys(self.last_config_schema))
                new_keys = set(self._extract_keys(current_schema))
                added = new_keys - old_keys
                removed = old_keys - new_keys

                if added or removed:
                    parts = []
                    if added:
                        parts.append(f"新增配置项: {', '.join(sorted(added))}")
                    if removed:
                        parts.append(f"移除配置项: {', '.join(sorted(removed))}")
                    return DriftResult(
                        severity="warning" if added else "info",
                        title="配置 Schema 变化",
                        description="; ".join(parts),
                        source="/api/config/schema",
                        detected_at=datetime.utcnow().isoformat() + "Z",
                        impact="低 — 观测台自适应渲染会处理新配置项",
                    )
            self.last_config_schema = current_schema
        except Exception as e:
            logger.debug(f"Config schema check failed: {e}")
        return None

    def check_file_structure(self, known_paths: list) -> list:
        """第 3 层：文件结构探测"""
        drifts = []
        for path_info in known_paths:
            path = self.hermes_home / path_info["path"]
            expected = path_info.get("expected", True)
            exists = path.exists()

            if expected and not exists:
                drifts.append(DriftResult(
                    severity="warning",
                    title="文件消失",
                    description=f"预期存在的文件/目录不存在: {path_info['path']}",
                    source="文件系统扫描",
                    detected_at=datetime.utcnow().isoformat() + "Z",
                    impact="中 — 对应采集器将进入降级模式",
                ))
            elif not expected and exists:
                drifts.append(DriftResult(
                    severity="info",
                    title="新增文件",
                    description=f"发现新文件/目录: {path_info['path']}",
                    source="文件系统扫描",
                    detected_at=datetime.utcnow().isoformat() + "Z",
                    impact="低 — 观测台将评估是否需要新增采集器",
                ))
        return drifts

    def check_event_format(self, event: dict) -> Optional[DriftResult]:
        """第 4 层：事件格式探测（实时）"""
        event_type = event.get("type", "")
        tool = event.get("tool", "")
        action = event.get("action", "")

        # 检查未知事件类型
        if event_type and event_type not in self.KNOWN_EVENT_TYPES:
            return DriftResult(
                severity="info",
                title="新事件类型",
                description=f"发现未知事件类型: {event_type}",
                source="Plugin Hook 事件流",
                detected_at=datetime.utcnow().isoformat() + "Z",
                impact="无 — 自适应渲染已处理",
            )

        # 检查未知工具 action
        if tool == "skill_manage" and action and action not in self.KNOWN_SKILL_ACTIONS:
            return DriftResult(
                severity="info",
                title="新 skill_manage action",
                description=f"skill_manage 新增 action: {action}",
                source="Plugin Hook 事件流",
                detected_at=datetime.utcnow().isoformat() + "Z",
                impact="无 — 自适应渲染已处理",
            )

        if tool == "memory" and action and action not in self.KNOWN_MEMORY_ACTIONS:
            return DriftResult(
                severity="info",
                title="新 memory action",
                description=f"memory 新增 action: {action}",
                source="Plugin Hook 事件流",
                detected_at=datetime.utcnow().isoformat() + "Z",
                impact="无 — 自适应渲染已处理",
            )
        return None

    def run_all_checks(self, known_paths: list = None) -> list:
        """执行所有 Drift 检测"""
        drifts = []
        r = self.check_version()
        if r:
            drifts.append(r)
        r = self.check_config_schema()
        if r:
            drifts.append(r)
        if known_paths:
            drifts.extend(self.check_file_structure(known_paths))
        return drifts

    def log_drift(self, drift: DriftResult):
        """记录 Drift 到日志文件"""
        try:
            self._drift_log_file.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "severity": drift.severity,
                "title": drift.title,
                "description": drift.description,
                "source": drift.source,
                "detected_at": drift.detected_at,
                "impact": drift.impact,
            }
            with open(self._drift_log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to log drift: {e}")

    def _extract_keys(self, schema: dict, prefix: str = "") -> set:
        """递归提取 Schema 中的所有键"""
        keys = set()
        if isinstance(schema, dict):
            for k, v in schema.items():
                full_key = f"{prefix}.{k}" if prefix else k
                keys.add(full_key)
                if isinstance(v, dict):
                    keys.update(self._extract_keys(v, full_key))
        return keys
