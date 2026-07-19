# -*- coding: utf-8 -*-
"""Hermes 进化观测台 — 后端配置"""
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


def _find_hermes_root() -> Path:
    """定位 ~/.hermes 根目录（与 active profile 无关）"""
    hh = os.environ.get("HERMES_HOME")
    if hh:
        hh_p = Path(hh)
        # HERMES_HOME 若指向 .../profiles/<name>，则根为祖父目录
        if hh_p.parent.name == "profiles":
            return hh_p.parent.parent
        return hh_p
    real_home = os.environ.get("HERMES_REAL_HOME") or str(Path.home())
    return Path(real_home) / ".hermes"


def get_hermes_home(profile: Optional[str] = None) -> Path:
    """获取指定 profile 的数据根目录。

    - profile 未指定或为 "default"：返回 ~/.hermes（default profile 的数据就在根目录）
    - profile=<name>：返回 ~/.hermes/profiles/<name>
    """
    root = _find_hermes_root()
    if not profile or profile == "default":
        return root
    return root / "profiles" / profile


@dataclass
class ObservatoryConfig:
    """观测台自身配置"""
    host: str = "127.0.0.1"
    port: int = 9120
    # Hermes Dashboard 地址（用于 /api/status 和 /api/config/schema）
    hermes_dashboard_url: str = "http://127.0.0.1:9119"
    # 数据采集间隔（秒）
    collect_interval: int = 60
    # Drift 检测间隔（秒）
    drift_check_interval: int = 3600
    # evolution-events.jsonl 轮转天数
    event_log_retention_days: int = 30
    # 前端静态文件目录
    frontend_dir: str = str(Path(__file__).parent.parent / "frontend")
    # 是否启用 WebSocket 实时推送
    enable_websocket: bool = True
    # 日志级别
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "ObservatoryConfig":
        return cls(
            host=os.environ.get("OBS_HOST", "127.0.0.1"),
            port=int(os.environ.get("OBS_PORT", "9120")),
            hermes_dashboard_url=os.environ.get("HERMES_DASHBOARD_URL", "http://127.0.0.1:9119"),
            collect_interval=int(os.environ.get("OBS_COLLECT_INTERVAL", "60")),
            drift_check_interval=int(os.environ.get("OBS_DRIFT_INTERVAL", "3600")),
            log_level=os.environ.get("OBS_LOG_LEVEL", "INFO"),
        )


config = ObservatoryConfig.from_env()
