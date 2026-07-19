"""Evolution Observatory Hook — 进化事件采集器

Hermes plugin 加载器会在插件目录导入 `__init__.py` 并调用 register(ctx)。
真正实现在 handler.py，这里做 re-export，保持插件目录清晰。
"""
from .handler import register

__all__ = ["register"]
