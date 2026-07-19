# -*- coding: utf-8 -*-
"""采集器基类 — 所有数据源采集器的抽象接口"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class CollectorResult:
    """采集器返回结果"""
    source: str           # 数据源名称
    data: Any             # 采集到的数据
    schema_version: str   # 数据的 Schema 版本
    status: str = "ok"    # ok / warning / error / unavailable
    error: Optional[str] = None
    timestamp: str = ""   # ISO 格式时间戳


class BaseCollector(ABC):
    """采集器抽象基类

    每个采集器负责读取一个 Hermes 数据源，返回标准化的 CollectorResult。
    采集器是只读的——永远不修改 Hermes 的任何文件。
    """

    # 数据源名称（唯一标识）
    name: str = "base"
    # 数据源路径模式（用于文件结构探测）
    path_pattern: str = ""
    # 已知 Schema 版本
    known_schema_version: str = "v1"

    def __init__(self, hermes_home: Path):
        self.hermes_home = hermes_home

    @abstractmethod
    def collect(self) -> CollectorResult:
        """执行采集，返回结果

        实现要求：
        - 只读访问，不修改任何文件
        - 文件不存在时返回 status="unavailable"，不抛异常
        - 读取失败时返回 status="error" + error 信息，不抛异常
        - 成功时返回 status="ok" + data
        """
        ...

    def check_exists(self) -> bool:
        """检查数据源是否存在"""
        if not self.path_pattern:
            return True
        path = self.hermes_home / self.path_pattern
        return path.exists()

    def get_schema(self) -> dict:
        """返回此采集器已知的 Schema 定义（用于 Drift 检测）"""
        return {"source": self.name, "version": self.known_schema_version}
