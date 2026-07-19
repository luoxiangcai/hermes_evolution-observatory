# -*- coding: utf-8 -*-
"""Hermes 进化观测台 — FastAPI 后端入口"""
import asyncio
import functools
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from config import config, get_hermes_home
from collectors import CollectorRegistry
from collectors.base import CollectorResult
from schema_registry import SchemaRegistry
from narrative_generator import NarrativeGenerator

# ━━ Logging ━━
logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("evolution-observatory")


# ━━ TTL 缓存 ━━
_TTL_CACHE: dict = {}

def ttl_cache(ttl_seconds: float):
    """按参数缓存 async 函数结果，TTL 秒后失效"""
    def deco(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            key = (fn.__name__, args, tuple(sorted(kwargs.items())))
            now = time.time()
            hit = _TTL_CACHE.get(key)
            if hit and hit[1] > now:
                return hit[0]
            result = await fn(*args, **kwargs)
            _TTL_CACHE[key] = (result, now + ttl_seconds)
            return result
        return wrapper
    return deco

# ━━ FastAPI ━━
app = FastAPI(
    title="Hermes 进化观测台",
    description="横切在所有进化机制之上的观测与编排层",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ━━ 全局状态 ━━
registries: dict[str, CollectorRegistry] = {}
schema_registries: dict[str, SchemaRegistry] = {}
narrative_generators: dict[str, NarrativeGenerator] = {}
websocket_clients: list[WebSocket] = []


def get_registry(profile: str = "default") -> CollectorRegistry:
    """获取或创建指定 Profile 的采集器注册表"""
    if profile not in registries:
        hermes_home = get_hermes_home(profile)
        registries[profile] = CollectorRegistry(
            hermes_home=hermes_home,
            evolution_output_dir=Path("output"),
        )
        schema_registries[profile] = SchemaRegistry(
            hermes_home=hermes_home,
            dashboard_url=config.hermes_dashboard_url,
        )
        narrative_generators[profile] = NarrativeGenerator(hermes_home=hermes_home)
    return registries[profile]


def get_schema_registry(profile: str = "default") -> SchemaRegistry:
    get_registry(profile)  # 确保已初始化
    return schema_registries[profile]


def get_narrative_generator(profile: str = "default") -> NarrativeGenerator:
    get_registry(profile)
    return narrative_generators[profile]


# ━━ REST API ━━

@app.get("/api/overview")
@ttl_cache(10)
async def get_overview(profile: str = Query("default")):
    """总览仪表盘数据"""
    registry = get_registry(profile)
    results = registry.collect_all()

    # 聚合统计
    skills_data = results.get("skills")
    skill_count = 0
    agent_created = 0
    if skills_data and skills_data.status == "ok" and skills_data.data:
        skill_count = skills_data.data.get("total_count", 0)
        for s in skills_data.data.get("skills", []):
            if s.get("created_by") == "agent":
                agent_created += 1

    memory_data = results.get("memory")
    memory_usage = 0
    if memory_data and memory_data.status == "ok" and memory_data.data:
        mem = memory_data.data.get("memory", {})
        memory_usage = mem.get("usage_percent", 0)

    events_data = results.get("events")
    event_count = 0
    if events_data and events_data.status == "ok" and events_data.data:
        event_count = events_data.data.get("total", 0)

    pending_data = results.get("pending")
    pending_count = 0
    if pending_data and pending_data.status == "ok" and pending_data.data:
        pending_count = pending_data.data.get("total", 0)

    return {
        "profile": profile,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "stats": {
            "skill_count": skill_count,
            "agent_created_skills": agent_created,
            "memory_usage_percent": memory_usage,
            "total_events": event_count,
            "pending_count": pending_count,
        },
        "collector_status": {
            name: {"status": r.status, "error": r.error}
            for name, r in results.items()
        },
    }


@app.get("/api/timeline")
async def get_timeline(
    profile: str = Query("default"),
    limit: int = Query(50, le=500),
    all_profiles: bool = Query(True, description="跨所有 profile 混排（默认 True 以匹配观测台样表跨 profile 视图）"),
):
    """进化时间线 — 支持跨 profile 混排"""
    registry = get_registry(profile)
    events_col = registry._collectors.get("events") if hasattr(registry, "_collectors") else None
    if events_col is None:
        # 兜底：老路径
        result = registry.collect_one("events")
    else:
        try:
            result = events_col.collect(all_profiles=all_profiles)
        except TypeError:
            # 采集器不支持该参数
            result = events_col.collect()
    if not result or result.status == "unavailable":
        return {"events": [], "total": 0, "profile": profile, "all_profiles": all_profiles}

    events = (result.data or {}).get("events", [])[:limit]
    sources = (result.data or {}).get("sources", [])
    return {"events": events, "total": len(events), "profile": profile,
            "all_profiles": all_profiles, "sources": sources}


@app.get("/api/memory")
async def get_memory(profile: str = Query("default")):
    """记忆状态"""
    registry = get_registry(profile)
    result = registry.collect_one("memory")
    if not result:
        raise HTTPException(404, "Memory collector not found")
    return result.data if result.status != "unavailable" else {"error": "unavailable", "status": result.status}


@app.get("/api/skills")
@ttl_cache(15)
async def get_skills(profile: str = Query("default")):
    """技能库"""
    registry = get_registry(profile)
    result = registry.collect_one("skills")
    if not result:
        raise HTTPException(404, "Skills collector not found")
    return result.data if result.status != "unavailable" else {"error": "unavailable", "status": result.status}


@app.get("/api/curator")
async def get_curator(profile: str = Query("default")):
    """Curator 活动"""
    registry = get_registry(profile)
    result = registry.collect_one("curator")
    if not result:
        raise HTTPException(404, "Curator collector not found")
    return result.data if result.status != "unavailable" else {"error": "unavailable", "status": result.status}


@app.get("/api/gepa")
async def get_gepa(profile: str = Query("default")):
    """GEPA 进化管道"""
    registry = get_registry(profile)
    result = registry.collect_one("gepa")
    if not result:
        raise HTTPException(404, "GEPA collector not found")
    return result.data if result.status != "unavailable" else {"error": "unavailable", "status": result.status}


@app.get("/api/pending")
async def get_pending(profile: str = Query("default")):
    """待审批写入"""
    registry = get_registry(profile)
    result = registry.collect_one("pending")
    if not result:
        raise HTTPException(404, "Pending collector not found")
    return result.data if result.status != "unavailable" else {"error": "unavailable", "status": result.status}


@app.get("/api/narrative")
@ttl_cache(20)
async def get_narrative(
    profile: str = Query("default"),
    days: int = Query(7, le=90),
    format: str = Query("json"),
):
    """进化叙事"""
    gen = get_narrative_generator(profile)
    if format == "markdown":
        from fastapi.responses import PlainTextResponse
        md = gen.generate_markdown(profile, days)
        return PlainTextResponse(md)
    return gen.generate(profile, days)


@app.get("/api/drift")
@ttl_cache(60)
async def get_drift(profile: str = Query("default")):
    """变化探测"""
    sr = get_schema_registry(profile)
    known_paths = [
        {"path": "memories/MEMORY.md", "expected": True},
        {"path": "memories/USER.md", "expected": True},
        {"path": "skills", "expected": True},
        {"path": "skills/.usage.json", "expected": True},
        {"path": "logs/curator", "expected": True},
        {"path": "logs/agent.log", "expected": True},
        {"path": "state.db", "expected": True},
        {"path": "pending", "expected": True},
    ]
    drifts = sr.run_all_checks(known_paths)
    return {
        "drifts": [
            {
                "severity": d.severity,
                "title": d.title,
                "description": d.description,
                "source": d.source,
                "detected_at": d.detected_at,
                "impact": d.impact,
            }
            for d in drifts
        ],
        "total": len(drifts),
        "hermes_version": sr.last_hermes_version,
    }


@app.get("/api/profiles")
async def get_profiles():
    """列出实际存在的 Hermes profile

    - `default` profile 的数据在 ~/.hermes/ 根目录
    - 其他 profile 在 ~/.hermes/profiles/<name>/
    - active profile 从 ~/.hermes/active_profile 文件读取（Hermes CLI 维护）
    """
    import os as _os
    from pathlib import Path as _P

    # 找 .hermes 根目录
    root = None
    hh = _os.environ.get("HERMES_HOME")
    if hh:
        hh_p = _P(hh)
        # 若 HERMES_HOME=.../profiles/<name>，则 root = .../.hermes（祖父目录）
        if hh_p.parent.name == "profiles":
            root = hh_p.parent.parent
        else:
            root = hh_p
    if root is None:
        real_home = _os.environ.get("HERMES_REAL_HOME") or str(_P.home())
        root = _P(real_home) / ".hermes"

    profiles = []

    # default profile = 根目录本身（当有 skills / memories / logs 时视为存在）
    root_markers = ["skills", "memories", "logs", "state.db"]
    if root.exists() and any((root / m).exists() for m in root_markers):
        profiles.append({"name": "default", "path": str(root)})

    # profiles/ 下的每个子目录
    profiles_dir = root / "profiles"
    if profiles_dir.exists():
        for p in sorted(profiles_dir.iterdir()):
            if p.is_dir() and not p.name.startswith("."):
                profiles.append({"name": p.name, "path": str(p)})

    # active profile：优先读 active_profile 文件，退回到从 HERMES_HOME 推断
    active = None
    active_file = root / "active_profile"
    if active_file.exists():
        try:
            active = active_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    if not active and hh:
        hh_p = _P(hh)
        if hh_p.parent.name == "profiles":
            active = hh_p.name
        elif hh_p == root:
            active = "default"

    return {
        "profiles": profiles,
        "count": len(profiles),
        "active": active,
        "root": str(root),
    }


@app.get("/api/checkpoints")
@ttl_cache(20)
async def get_checkpoints(
    profile: str = Query("default"),
    skill: Optional[str] = Query(None, description="仅返回该技能的快照；不传则返回全部"),
):
    """列出 skills/.checkpoints/ 下的历史快照

    返回：{skills: {<name>: [{file, timestamp, action, session, turn, size}...]}, total_*: N}
    """
    registry = get_registry(profile)
    res = registry.collect_one("checkpoints")
    if not res:
        return {"status": "unavailable", "skills": {}, "error": "checkpoints collector missing"}
    if res.status == "unavailable":
        return {"status": "unavailable", "skills": {}, "error": res.error, "hint":
                "checkpoints 由 evolution-observatory-hook 插件的 pre_tool 钩子在每次 skill_manage patch/edit 前写入。"
                "如果一直没触发过 patch/edit 就不会有目录，属正常降级。"}
    data = res.data or {}
    if skill:
        skill_snaps = (data.get("skills") or {}).get(skill, [])
        return {"status": "ok", "skill": skill, "snapshots": skill_snaps, "count": len(skill_snaps)}
    return {"status": "ok", **data}


@app.get("/api/checkpoint/diff")
@ttl_cache(30)
async def get_checkpoint_diff(
    profile: str = Query("default"),
    skill: str = Query(..., description="技能名"),
    from_file: Optional[str] = Query(None, description="旧快照文件名；不传则用倒数第二个"),
    to_file: Optional[str] = Query(None, description="新快照文件名；不传则用最新快照"),
    compare_current: bool = Query(True, description="to_file 未指定时，是否与当前 SKILL.md 比"),
):
    """对某个技能的两个快照做 unified diff。

    默认对比策略：
      - to_file 未指定 & compare_current=true  → 最新快照 vs 当前 SKILL.md
      - to_file 未指定 & compare_current=false → 倒数第二个 vs 最新（即最后一次 patch 的 diff）
    """
    import difflib
    registry = get_registry(profile)
    cp_res = registry.collect_one("checkpoints")
    if not cp_res or cp_res.status == "unavailable":
        return {"status": "unavailable", "error": (cp_res.error if cp_res else "checkpoints missing"),
                "hint": "尚未启用 Checkpoints 或该技能未发生过 patch/edit"}
    snaps = ((cp_res.data or {}).get("skills") or {}).get(skill, [])
    if not snaps:
        return {"status": "not_found", "error": f"技能 {skill} 无历史快照"}

    def _load(fname: str) -> Optional[str]:
        for s in snaps:
            if s.get("file") == fname:
                try:
                    return Path(s["path"]).read_text(encoding="utf-8", errors="replace")
                except Exception:
                    return None
        return None

    # 解析 from / to
    old_text = old_label = new_text = new_label = None
    if from_file:
        old_text = _load(from_file)
        old_label = from_file
    if to_file:
        new_text = _load(to_file)
        new_label = to_file

    if new_text is None and compare_current:
        # 与当前 SKILL.md 比
        skills_res = registry.collect_one("skills")
        skills = ((skills_res.data if skills_res else {}) or {}).get("skills", []) or []
        target = next((s for s in skills if s.get("name") == skill), None)
        if target and target.get("path"):
            try:
                # path 可能是相对（"skills/xxx/SKILL.md"）或绝对，两种都支持
                p = Path(target["path"])
                if not p.is_absolute():
                    p = Path(get_hermes_home(profile)) / p
                new_text = p.read_text(encoding="utf-8", errors="replace")
                new_label = "当前 SKILL.md"
            except Exception:
                pass
        if old_text is None:
            # 用最新快照做 old
            old_text = _load(snaps[-1]["file"])
            old_label = snaps[-1]["file"]
    elif new_text is None:
        # 用最新快照
        new_text = _load(snaps[-1]["file"])
        new_label = snaps[-1]["file"]
        if old_text is None and len(snaps) >= 2:
            old_text = _load(snaps[-2]["file"])
            old_label = snaps[-2]["file"]

    if old_text is None or new_text is None:
        return {"status": "insufficient", "error": "缺少可供对比的快照（至少需要 1 份快照 + 当前 SKILL.md，或 2 份快照）",
                "snapshots_available": len(snaps)}

    diff_lines = list(difflib.unified_diff(
        old_text.splitlines(),
        new_text.splitlines(),
        fromfile=old_label or "old",
        tofile=new_label or "new",
        lineterm="",
        n=3,
    ))
    # 统计
    added = sum(1 for ln in diff_lines if ln.startswith("+") and not ln.startswith("+++"))
    removed = sum(1 for ln in diff_lines if ln.startswith("-") and not ln.startswith("---"))
    return {
        "status": "ok",
        "skill": skill,
        "from": old_label,
        "to": new_label,
        "added_lines": added,
        "removed_lines": removed,
        "diff": diff_lines,
        "old_length": len(old_text),
        "new_length": len(new_text),
    }


@app.get("/api/reveal")
async def reveal_path(
    profile: str = Query("default"),
    path: str = Query(..., description="要打开的文件或目录路径（相对 hermes_home 或绝对）"),
):
    """在系统资源管理器中显示指定文件/目录（WSL: explorer.exe /select；Linux: xdg-open）。

    安全策略：仅允许打开 hermes_home、profile skills/memories/logs 或 evolution-observatory
    工作目录之下的路径；其他一律拒绝。
    """
    import subprocess
    from pathlib import Path as _P

    # 组装允许根目录白名单
    hh = _P(get_hermes_home(profile))
    obs_root = _P(__file__).resolve().parent.parent  # 项目根（本文件所在目录的父目录）
    allowed_roots = [hh.resolve(), obs_root.resolve()]
    # 若 HERMES_HOME 指向 profile 目录，把父级（hermes root）也加入
    parent = hh.parent
    if parent.name == "profiles":
        allowed_roots.append(parent.parent.resolve())

    try:
        p = _P(path)
        if not p.is_absolute():
            p = (hh / p).resolve()
        else:
            p = p.resolve()
    except Exception as e:
        return {"status": "error", "error": f"路径解析失败：{e}"}

    if not any(str(p).startswith(str(root)) for root in allowed_roots):
        return {"status": "denied", "error": f"路径不在白名单：{p}",
                "allowed_roots": [str(r) for r in allowed_roots]}
    if not p.exists():
        return {"status": "not_found", "error": f"路径不存在：{p}"}

    # 判定文件 or 目录：文件用 /select 高亮，目录直接打开
    is_dir = p.is_dir()
    try:
        if _is_wsl():
            # WSL：用 explorer.exe，需要 Windows 风格路径
            # systemd user service 的 PATH 可能没有 /mnt/c/Windows，做 fallback
            explorer = "explorer.exe"
            for candidate in ("explorer.exe", "/mnt/c/Windows/explorer.exe", "/mnt/c/Windows/System32/explorer.exe"):
                try:
                    if candidate == "explorer.exe":
                        subprocess.check_output(["which", "explorer.exe"], timeout=2, stderr=subprocess.DEVNULL)
                        explorer = "explorer.exe"; break
                    elif Path(candidate).exists():
                        explorer = candidate; break
                except Exception:
                    continue
            win_path = subprocess.check_output(
                ["wslpath", "-w", str(p)], text=True, timeout=3
            ).strip()
            if is_dir:
                subprocess.Popen([explorer, win_path])
                action = f"{explorer} {win_path}"
            else:
                subprocess.Popen([explorer, "/select,", win_path])
                action = f"{explorer} /select, {win_path}"
        else:
            # 纯 Linux：xdg-open 打开文件/目录（无法 select）
            target = str(p if is_dir else p.parent)
            subprocess.Popen(["xdg-open", target])
            action = f"xdg-open {target}"
        return {"status": "ok", "path": str(p), "is_dir": is_dir, "action": action}
    except Exception as e:
        return {"status": "error", "error": f"打开失败：{e}", "path": str(p)}


def _is_wsl() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except Exception:
        return False


@app.get("/api/file/view")
async def view_file(
    profile: str = Query("default"),
    path: str = Query(..., description="要查看的文件路径"),
    max_bytes: int = Query(200_000, ge=1, le=2_000_000, description="最大读取字节，超出截断"),
):
    """在浏览器里查看文件内容（白名单目录内的文本文件）。"""
    from pathlib import Path as _P

    hh = _P(get_hermes_home(profile))
    obs_root = _P(__file__).resolve().parent.parent  # 项目根
    allowed_roots = [hh.resolve(), obs_root.resolve()]
    parent = hh.parent
    if parent.name == "profiles":
        allowed_roots.append(parent.parent.resolve())

    try:
        p = _P(path)
        if not p.is_absolute():
            p = (hh / p).resolve()
        else:
            p = p.resolve()
    except Exception as e:
        return {"status": "error", "error": f"路径解析失败：{e}"}

    if not any(str(p).startswith(str(root)) for root in allowed_roots):
        return {"status": "denied", "error": f"路径不在白名单：{p}"}
    if not p.exists():
        return {"status": "not_found", "error": f"文件不存在：{p}"}
    if p.is_dir():
        return {"status": "is_directory", "error": "路径指向目录，不能作为文件查看"}

    try:
        raw = p.read_bytes()
        truncated = len(raw) > max_bytes
        content = raw[:max_bytes].decode("utf-8", errors="replace")
        stat = p.stat()
        return {
            "status": "ok",
            "path": str(p),
            "name": p.name,
            "size": stat.st_size,
            "mtime": datetime.utcfromtimestamp(stat.st_mtime).isoformat() + "Z",
            "truncated": truncated,
            "content": content,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/lineage")
@ttl_cache(20)
async def get_lineage(
    profile: str = Query("default"),
    skill: str = Query(..., description="技能名"),
):
    """从 .usage.json + curator 日志重建单个技能的历史谱系。

    数据源：
    - .usage.json 中 created_at / last_patched_at / last_used_at / patch_count / created_by
    - curator runs：查找涉及该技能的运行记录（若有）
    - 后续可扩展：SKILL.md 的 git 历史（如果整个 skills/ 是 git 仓库）
    """
    registry = get_registry(profile)
    skills_res = registry.collect_one("skills")
    if not skills_res or skills_res.status == "unavailable":
        return {"skill": skill, "status": "unavailable", "events": []}

    skills = (skills_res.data or {}).get("skills", []) or []
    target = next((s for s in skills if s.get("name") == skill), None)
    if not target:
        return {"skill": skill, "status": "not_found", "events": []}

    usage = target.get("usage") or {}
    events = []

    # 创建事件
    created_at = usage.get("created_at")
    created_by = target.get("created_by") or "unknown"
    if created_at:
        origin = "Agent-created" if created_by == "agent" else ("Bundled" if created_by in (None, "null") else str(created_by))
        events.append({
            "timestamp": created_at,
            "kind": "create",
            "label": "创建",
            "origin": origin,
            "detail": f"由 {origin} 创建",
        })

    # patch 事件（有 last_patched_at 但没有单次的详细列表——只能给汇总）
    patch_count = usage.get("patch_count") or 0
    last_patched = usage.get("last_patched_at")
    if patch_count > 0 and last_patched:
        events.append({
            "timestamp": last_patched,
            "kind": "patch",
            "label": f"最近一次 patch（累计 {patch_count} 次）",
            "origin": "skill_manage patch",
            "detail": f"patch_count={patch_count}",
        })

    # curator runs 涉及该技能
    curator_res = registry.collect_one("curator")
    if curator_res and curator_res.status != "unavailable":
        runs = (curator_res.data or {}).get("runs", []) or []
        for r in runs:
            actions = r.get("actions") or []
            for a in actions:
                if a.get("skill") == skill or a.get("target") == skill:
                    events.append({
                        "timestamp": r.get("timestamp", ""),
                        "kind": "curator",
                        "label": f"Curator {a.get('type','review')}",
                        "origin": "Curator",
                        "detail": a.get("reason") or a.get("detail") or "",
                    })

    # 从 evolution-events.jsonl 挖出针对该 skill 的每次事件（skill_manage patch/edit/create/delete/view）
    events_res = registry.collect_one("events")
    if events_res and events_res.status != "unavailable":
        raw_events = (events_res.data or {}).get("events", []) or []
        for ev in raw_events:
            if ev.get("type") != "skill":
                continue
            args = ev.get("args") or {}
            if args.get("name") != skill:
                continue
            action = ev.get("action") or ev.get("tool", "")
            kind_map = {
                "create": ("create", "创建"),
                "patch":  ("patch",  "Patch"),
                "edit":   ("patch",  "Edit"),
                "delete": ("archive","删除"),
                "write_file": ("patch", "写入文件"),
                "remove_file": ("patch", "删除文件"),
            }
            kind, label_zh = kind_map.get(action, ("patch", action or "skill_manage"))
            events.append({
                "timestamp": ev.get("timestamp", ""),
                "kind": kind,
                "label": f"{label_zh}",
                "origin": ev.get("origin") or "skill_manage",
                "detail": ev.get("desc") or "",
                "session": ev.get("session", ""),
                "turn": ev.get("turn", 0),
            })

    # 从 checkpoints 采集器挖出每次快照（有真实 diff 可展开）
    cp_res = registry.collect_one("checkpoints")
    has_checkpoints = False
    if cp_res and cp_res.status != "unavailable":
        cp_snaps = ((cp_res.data or {}).get("skills") or {}).get(skill, []) or []
        for snap in cp_snaps:
            has_checkpoints = True
            events.append({
                "timestamp": snap.get("timestamp") or snap.get("mtime"),
                "kind": "checkpoint",
                "label": f"快照（{snap.get('action') or 'patch'} 前）",
                "origin": "checkpoint pre_tool hook",
                "detail": f"文件 {snap.get('file')} · {snap.get('size',0)}B",
                "checkpoint_file": snap.get("file"),
                "checkpoint_path": snap.get("path"),  # 绝对路径，前端可点开
                "session": snap.get("session", ""),
                "turn": snap.get("turn", 0),
            })

    # 最近使用（不算进化事件，作为"当前状态"锚点）
    last_used = usage.get("last_used_at")
    state = target.get("state")
    # 按时间排，同时间保留 create 在前
    events.sort(key=lambda e: (e.get("timestamp", ""), 0 if e.get("kind")=="create" else 1))

    # 生成能力提示（诚实说明当前系统能到什么程度）
    if has_checkpoints:
        cap_note = (
            "谱系基于真实事件（.usage.json + evolution-events.jsonl + curator runs + checkpoints）。"
            "✅ Checkpoints 已启用——每次 skill_manage patch/edit 前都会保存 SKILL.md 快照，"
            "点击带 📸 图标的事件可以看到该次 patch 的真实 unified diff。"
        )
    else:
        cap_note = (
            "谱系基于真实事件（.usage.json + evolution-events.jsonl + curator runs）。"
            "⚠️ 当前 Checkpoints 尚无该技能的快照——插件已注册 pre_tool 钩子（每次 skill_manage patch/edit 前"
            "会拍一份 SKILL.md 快照到 skills/.checkpoints/<name>/），需要一次真实 patch 才会生成第一份。"
        )
    capabilities = {
        "has_semver": False,
        "has_diff": has_checkpoints,
        "has_snapshots": has_checkpoints,
        "note": cap_note,
    }

    return {
        "skill": skill,
        "status": "ok",
        "state": state,
        "created_by": created_by,
        "abs_path": target.get("abs_path"),
        "view_count": usage.get("view_count", 0),
        "use_count": usage.get("use_count", 0),
        "patch_count": patch_count,
        "last_used_at": last_used,
        "events": events,
        "total_events": len(events),
        "capabilities": capabilities,
    }


@app.get("/api/skills/history")
@ttl_cache(20)
async def get_skills_history(
    profile: str = Query("default"),
    days: int = Query(30, le=365),
):
    """技能库随时间的累计增长（按 created_at 聚合）"""
    from datetime import timedelta
    registry = get_registry(profile)
    result = registry.collect_one("skills")
    if not result or result.status == "unavailable":
        return {"buckets": [], "days": days, "total": 0}

    skills = (result.data or {}).get("skills", []) or []
    # 收集所有 created_at
    created_dates = []
    for s in skills:
        u = s.get("usage") or {}
        c = u.get("created_at")
        if c:
            try:
                created_dates.append(datetime.fromisoformat(c.replace("Z", "+00:00")).date())
            except Exception:
                pass

    # 生成 N 天桶（截止今天，UTC）
    today = datetime.utcnow().date()
    buckets = []
    running_total = 0
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        added_today = sum(1 for cd in created_dates if cd == d)
        # 累计 = 该日以前（含）创建的总数
        cumulative = sum(1 for cd in created_dates if cd <= d)
        buckets.append({
            "date": d.isoformat(),
            "added": added_today,
            "cumulative": cumulative,
        })
        running_total = cumulative

    return {
        "buckets": buckets,
        "days": days,
        "total": running_total,
        "total_created_seen": len(created_dates),
    }


@app.get("/api/pareto")
async def get_pareto(profile: str = Query("default")):
    """GEPA 帕累托前沿数据"""
    registry = get_registry(profile)
    result = registry.collect_one("gepa")
    if not result or result.status == "unavailable":
        return {"points": [], "status": "unavailable", "error": (result.error if result else "gepa collector missing")}

    runs = (result.data or {}).get("runs", []) or []
    points = []
    for r in runs:
        m = r.get("metrics") or {}
        acc = m.get("evolved_score") or m.get("accuracy")
        cost = m.get("cost") or m.get("tokens") or m.get("duration_s")
        if acc is not None and cost is not None:
            points.append({
                "skill": r.get("skill_name", ""),
                "acc": acc,
                "cost": cost,
                "iterations": m.get("iterations") or m.get("n_iterations", 0),
            })
    return {"points": points, "total": len(points)}


@app.get("/api/health")
async def get_health(profile: str = Query("default")):
    """数据源健康检查"""
    registry = get_registry(profile)
    return {"sources": registry.get_health(), "profile": profile}


@app.get("/api/schemas")
async def get_schemas(profile: str = Query("default")):
    """所有采集器的 Schema 定义"""
    registry = get_registry(profile)
    return {"schemas": registry.get_all_schemas(), "profile": profile}


@app.post("/api/events")
async def post_event(event: dict, profile: str = Query("default")):
    """接收 Plugin Hook 推送的进化事件"""
    registry = get_registry(profile)
    events_collector = registry.get("events")
    if not events_collector:
        raise HTTPException(404, "Events collector not found")

    # 补充元数据
    if "timestamp" not in event:
        event["timestamp"] = datetime.utcnow().isoformat() + "Z"
    if "profile" not in event:
        event["profile"] = profile

    # Drift 检测
    sr = get_schema_registry(profile)
    drift = sr.check_event_format(event)
    if drift:
        sr.log_drift(drift)
        # 通过 WebSocket 推送 Drift 告警
        await broadcast({"type": "drift", "data": {
            "severity": drift.severity,
            "title": drift.title,
            "description": drift.description,
        }})

    # 写入事件日志
    success = events_collector.append_event(event)
    if not success:
        raise HTTPException(500, "Failed to write event")

    # 通过 WebSocket 推送事件
    await broadcast({"type": "event", "data": event})

    return {"status": "ok", "event": event}


# ━━ WebSocket ━━

@app.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    """WebSocket 实时事件推送"""
    await ws.accept()
    websocket_clients.append(ws)
    logger.info(f"WebSocket client connected. Total: {len(websocket_clients)}")
    try:
        while True:
            # 保持连接，等待客户端消息（心跳）
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        websocket_clients.remove(ws)
        logger.info(f"WebSocket client disconnected. Total: {len(websocket_clients)}")


async def broadcast(message: dict):
    """向所有 WebSocket 客户端广播消息"""
    text = json.dumps(message, ensure_ascii=False)
    for client in websocket_clients:
        try:
            await client.send_text(text)
        except Exception:
            pass


# ━━ 前端静态文件 ━━

frontend_path = Path(config.frontend_dir)
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")


@app.get("/")
async def index():
    """返回前端页面"""
    index_file = frontend_path / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return JSONResponse({"message": "Frontend not found. Place index.html in frontend/ dir."})


# ━━ 启动 ━━

def main():
    """命令行入口 — 由 pyproject.toml 的 [project.scripts] 暴露为 evolution-observatory 命令"""
    import uvicorn
    logger.info(f"Starting Hermes Evolution Observatory on {config.host}:{config.port}")
    logger.info(f"Hermes home: {get_hermes_home()}")
    uvicorn.run(app, host=config.host, port=config.port, log_level=config.log_level.lower())


if __name__ == "__main__":
    main()
