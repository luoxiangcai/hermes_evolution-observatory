# -*- coding: utf-8 -*-
"""Hermes Plugin Hook — 进化事件采集器

安装方式：将此目录复制到 ~/.hermes/plugins/evolution-observatory-hook/
Hermes 启动时会自动加载此插件。

插件功能：
- 监听 post_tool 事件，匹配 memory / skill_manage / skill_view 工具调用
- 将进化相关事件写入 ~/.hermes/logs/evolution-events.jsonl
- 事件通过 HTTP POST 推送到观测台后端（如果运行中）
"""
import json
import os
import httpx
from pathlib import Path
from datetime import datetime
from typing import Optional


# 观测台后端端点（用于实时推送）
OBSERVATORY_URL = os.getenv("EVOLUTION_OBSERVATORY_URL", "http://127.0.0.1:9120")


def _hermes_home() -> Path:
    """解析当前 Hermes profile 的家目录。
    优先级：$HERMES_HOME > ~/.hermes/active_profile 指向的 profile > ~/.hermes 根
    """
    env = os.getenv("HERMES_HOME")
    if env:
        return Path(env).expanduser().resolve()
    active = Path.home() / ".hermes" / "active_profile"
    if active.exists():
        try:
            name = active.read_text(encoding="utf-8").strip()
            if name and name != "default":
                return (Path.home() / ".hermes" / "profiles" / name).resolve()
        except Exception:
            pass
    return (Path.home() / ".hermes").resolve()


def _events_file() -> Path:
    return _hermes_home() / "logs" / "evolution-events.jsonl"


def _current_profile() -> str:
    """当前 profile 名（default 或 profiles/<name> 的最后一段）"""
    hh = _hermes_home()
    if hh.parent.name == "profiles":
        return hh.name
    return "default"


# 需要监听的进化相关工具
EVOLUTION_TOOLS = {"memory", "skill_manage", "skill_view"}

# 当前 session 上下文（由 Hermes 注入）
_current_session_id = None
_current_turn = 0


def register(ctx):
    """插件注册入口 — Hermes 启动时调用"""
    ctx.register_hook("pre_tool", _on_pre_tool)  # ← 新增：patch/edit 前拍快照
    ctx.register_hook("post_tool", _on_post_tool)
    ctx.register_hook("on_session_start", _on_session_start)
    ctx.register_hook("on_session_end", _on_session_end)
    ctx.register_hook("post_llm_call", _on_post_llm_call)
    ctx.logger.info("Evolution Observatory Hook registered (with checkpoints)")


# ═══════════ Checkpoint 机制 ═══════════
# 每次 skill_manage patch/edit 前，把当前 SKILL.md 存一份到 .checkpoints/<name>/<ts>.md
# 每个技能保留最近 MAX_CHECKPOINTS 份，超出自动删最老
MAX_CHECKPOINTS = 50
CHECKPOINT_ACTIONS = {"patch", "edit"}


def _skills_root() -> Path:
    """定位当前 profile 的 skills 目录。HERMES_HOME 若指向 profile 目录则直接用其 skills/"""
    hh = os.environ.get("HERMES_HOME")
    if hh:
        p = Path(hh) / "skills"
        if p.exists():
            return p
    return Path.home() / ".hermes" / "skills"


def _find_skill_dir(skills_root: Path, name: str) -> Optional[Path]:
    """在 skills/ 下（含分类子目录）找到 SKILL.md 所在目录"""
    if not name:
        return None
    # 一级：skills/<name>/SKILL.md
    direct = skills_root / name
    if (direct / "SKILL.md").exists():
        return direct
    # 二级：skills/<category>/<name>/SKILL.md
    try:
        for sub in skills_root.iterdir():
            if not sub.is_dir():
                continue
            cand = sub / name
            if (cand / "SKILL.md").exists():
                return cand
    except Exception:
        pass
    return None


def _snapshot_skill(name: str, action: str) -> Optional[Path]:
    """把当前 SKILL.md 拍一份快照。永不 raise。"""
    try:
        skills_root = _skills_root()
        skill_dir = _find_skill_dir(skills_root, name)
        if not skill_dir:
            return None  # 技能不存在（create 情况）或路径不对，直接跳过
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return None
        cp_dir = skills_root / ".checkpoints" / name
        cp_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
        cp_file = cp_dir / f"{ts}.md"
        # 用 read+write 而不是 shutil.copy，避免权限/mtime 问题
        cp_file.write_text(skill_md.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
        # 记录 metadata 到同目录 .meta.jsonl（追加）
        meta = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": action,
            "session": _current_session_id or "",
            "turn": _current_turn,
            "file": cp_file.name,
            "size": cp_file.stat().st_size,
        }
        (cp_dir / ".meta.jsonl").open("a", encoding="utf-8").write(json.dumps(meta, ensure_ascii=False) + "\n")
        # 修剪超额快照
        _prune_checkpoints(cp_dir)
        return cp_file
    except Exception as e:
        try:
            import logging
            logging.getLogger("evolution-observatory-hook").debug(f"snapshot failed for {name}: {e}")
        except Exception:
            pass
        return None


def _prune_checkpoints(cp_dir: Path):
    """保留最近 MAX_CHECKPOINTS 份，删除更老的（.meta.jsonl 不动，用作长期审计）"""
    try:
        files = sorted([p for p in cp_dir.iterdir() if p.is_file() and p.suffix == ".md"])
        if len(files) <= MAX_CHECKPOINTS:
            return
        for old in files[:-MAX_CHECKPOINTS]:
            try:
                old.unlink()
            except Exception:
                pass
    except Exception:
        pass


def _on_pre_tool(ctx, data):
    """工具调用前 — 若是 skill_manage patch/edit，拍快照"""
    try:
        if data.get("tool", "") != "skill_manage":
            return
        action = data.get("action") or (data.get("args") or {}).get("action") or ""
        if action not in CHECKPOINT_ACTIONS:
            return
        name = (data.get("args") or {}).get("name")
        if name:
            _snapshot_skill(name, action)
    except Exception:
        # 永不阻塞原工具调用
        pass


def _on_session_start(ctx, data):
    """会话开始"""
    global _current_session_id, _current_turn
    _current_session_id = data.get("session_id", "")
    _current_turn = 0


def _on_session_end(ctx, data):
    """会话结束"""
    global _current_session_id, _current_turn
    _current_session_id = None
    _current_turn = 0


def _on_post_llm_call(ctx, data):
    """LLM 调用后 — turn 计数"""
    global _current_turn
    _current_turn += 1


def _on_post_tool(ctx, data):
    """工具调用后 — 核心事件采集"""
    tool_name = data.get("tool", "")
    if tool_name not in EVOLUTION_TOOLS:
        return

    # 构建进化事件
    event = _build_event(tool_name, data)

    # 写入本地日志
    _write_event(event)

    # 推送到观测台后端（如果运行中）
    _push_to_observatory(event)


def _build_event(tool_name: str, data: dict) -> dict:
    """构建结构化进化事件"""
    action = data.get("action", "")
    result = data.get("result", "")
    args = data.get("args", {})

    # 推断事件类型
    if tool_name == "memory":
        event_type = "memory"
        desc = _describe_memory_event(action, args, result)
    elif tool_name == "skill_manage":
        event_type = "skill"
        desc = _describe_skill_event(action, args, result)
    elif tool_name == "skill_view":
        event_type = "skill"
        desc = f"查看技能: {args.get('name', 'unknown')}"
    else:
        event_type = "unknown"
        desc = f"{tool_name}: {action}"

    # 推断触发源
    origin = _infer_origin(data)

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "type": event_type,
        "tool": tool_name,
        "action": action,
        "desc": desc,
        "origin": origin,
        "session": _current_session_id or "",
        "turn": _current_turn,
        "args": _safe_args(args),
    }


def _describe_memory_event(action: str, args: dict, result: str) -> str:
    """生成记忆事件的描述"""
    target = args.get("target", "memory")
    if action == "add":
        content = args.get("content", "")[:80]
        return f"添加 {target} 条目: {content}..."
    elif action == "replace":
        return f"替换 {target} 条目"
    elif action == "remove":
        return f"移除 {target} 条目"
    return f"memory {action}"


def _describe_skill_event(action: str, args: dict, result: str) -> str:
    """生成技能事件的描述"""
    name = args.get("name", "unknown")
    if action == "create":
        return f"创建新技能: {name}"
    elif action == "patch":
        return f"修补技能: {name}"
    elif action == "edit":
        return f"编辑技能: {name}"
    elif action == "delete":
        return f"删除技能: {name}"
    elif action == "write_file":
        return f"写入技能辅助文件: {name}"
    elif action == "remove_file":
        return f"删除技能辅助文件: {name}"
    return f"skill_manage {action}: {name}"


def _infer_origin(data: dict) -> str:
    """推断事件触发源"""
    # Hermes 的 post_tool hook data 中可能包含 write_origin
    write_origin = data.get("write_origin", "")
    if write_origin == "background_review":
        return "background_review fork"
    if write_origin == "foreground":
        return "foreground turn"
    # 如果没有明确标记，根据 session 上下文推断
    if _current_turn > 0:
        return "foreground turn"
    return "unknown"


def _safe_args(args: dict) -> dict:
    """清理 args 中的敏感信息"""
    safe = {}
    for k, v in args.items():
        if k in ("content", "new_string", "file_content"):
            safe[k] = str(v)[:200]  # 截断长内容
        elif k in ("old_string", "old_text"):
            safe[k] = str(v)[:100]
        else:
            safe[k] = v
    return safe


def _write_event(event: dict):
    """写入本地事件日志（写到当前 profile 的 logs/evolution-events.jsonl）"""
    try:
        # 自动补 profile 字段（若 hook 层没传）
        event.setdefault("profile", _current_profile())
        f = _events_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as e:
        ctx_logger = __import__("logging").getLogger("evolution-observatory-hook")
        ctx_logger.error(f"Failed to write event: {e}")


def _push_to_observatory(event: dict):
    """推送到观测台后端"""
    try:
        httpx.post(
            f"{OBSERVATORY_URL}/api/events",
            json=event,
            timeout=2,
        )
    except Exception:
        pass  # 观测台未运行时静默跳过
