<div align="right">

🇨🇳 中文 · [🇺🇸 English](README.en.md)

</div>

# Hermes 观测台 · Hermes Observatory

> 让 Hermes Agent 的每一次自我进化和多 Agent 协作，从**黑盒**里走出来。

>

> **可观测 · 可追溯 · 可解释 · 可干预 · 可回滚。**

[![tests](https://img.shields.io/badge/tests-17%20passed-brightgreen)]()
[![python](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![license](https://img.shields.io/badge/license-MIT-green)]()
[![status](https://img.shields.io/badge/status-alpha-orange)]()

---

## 💡 项目要解决的问题

[**Hermes Agent**](https://hermes-agent.nousresearch.com) 是 Nous Research 开源的 AI Agent 框架。它有两个核心能力让传统 Agent 望尘莫及：

### 1. 自我进化

- **memory** 持续更新长期记忆（`MEMORY.md` / `USER.md`）
- **skill_manage** 让 Agent 自己创建、修补、归档"技能"
- **curator** 定期整理技能库、归档久未使用的技能
- **GEPA / DSPy** 用遗传算法离线优化技能提示词
- **background_review** 后台复盘，把成功经验沉淀成新技能
- **Checkpoints** 每次改动前自动打快照

### 2. 多 Agent 协作

- **delegate_task** 父 Agent spawn 子 Agent，并行处理子任务
- **Kanban** 持久化任务看板（`~/.hermes/kanban.db`），跨 Profile 共享
- **Dispatcher** 自动调度 Worker 进程执行看板任务
- **多 Profile** 每个 Profile 是独立的 Agent 实例，有自己的技能/记忆/会话

这些机制默默运行、独立演化——但**问题也在这里**：

> 🔒 **进化和协作都在"黑盒"里发生。使用者看不到、看不懂、不可干预、不可回溯。**

- ❓ Agent 今天到底学到了什么？沉淀了哪些新技能？为什么？
- ❓ MEMORY.md 又更新了，具体加了什么？覆盖了什么？
- ❓ GEPA 这次进化让技能变好了还是变差了？我怎么回滚？
- ❓ 哪个 Agent 正在工作？哪个空闲？它在做什么任务？
- ❓ Kanban 看板上的任务进展到什么阶段了？有没有卡住的？
- ❓ 多个 Agent 之间的委派关系是什么？谁在等谁的结果？

## 界面演示

> 下图是实际运行中的界面（点击截图可放大看）。此外还有一份**带完整演示数据的交互原型** 👇

<div align="center">
  <a href="https://luoxiangcai.github.io/hermes_observatory/demo.html" target="_blank">
    <img src="https://img.shields.io/badge/🌐_在线演示-点击打开可交互页面-blue?style=for-the-badge" alt="在线演示">
  </a>
  <br>
  <sub>💡 包含进化观测 + 协作观测 + 双主题切换的完整演示</sub>
</div>

<br>

<table>
  <tr>
    <td align="center"><b>总览 · 仪表盘</b></td>
    <td align="center"><b>进化时间线</b></td>
  </tr>
  <tr>
    <td><img src="screenshots/overview.png" alt="总览仪表盘" width="400"></td>
    <td><img src="screenshots/timeline.png" alt="进化时间线" width="400"></td>
  </tr>
  <tr>
    <td align="center"><b>技能库</b></td>
    <td align="center"><b>进化谱系树</b></td>
  </tr>
  <tr>
    <td><img src="screenshots/skills.png" alt="技能库" width="400"></td>
    <td><img src="screenshots/lineage.png" alt="进化谱系树" width="400"></td>
  </tr>
</table>

## 🎯 项目目标

**让进化和协作都"看得见"。**

Hermes 观测台包含**两大观测模块**，通过侧边栏 Tab 一键切换：

### 🧬 进化观测

| 能力 | 具体做什么 |
|---|---|
| 👁 **可观测** | 11 个只读采集器扫真实 Hermes 数据源，把散落在 `~/.hermes/**` 各处的进化事件汇聚成时间线、谱系树、状态卡片 |
| 🔍 **可追溯** | 每个技能从 v1.0 到当前版本的完整谱系；每次记忆修改的 session/turn 溯源；点击跳回原始上下文 |
| 📖 **可解释** | 每个进化事件都标注**触发源**（foreground / background_review / Curator / GEPA），不再是"莫名其妙就变了" |
| ✋ **可干预** | 敏感/可疑写入进入"待审批"队列，用户手动放行或拒绝，Agent 无法绕过 |
| ⏪ **可回滚** | Checkpoints 在每次 patch/edit 前自动打快照，任何时候可以"回到那一刻"—— diff 对比 + 一键回滚 |

**13 个视图**：总览仪表盘 · 进化时间线 · 记忆状态 · 技能库 · Curator 活动 · GEPA 进化管道 · 进化谱系树 · 待审批写入 · 进化叙事 · 系统架构 · 四判据检验 · 术语表 · 变化探测

### 🤝 协作观测台

| 能力 | 具体做什么 |
|---|---|
| 🤖 **Agent 活动监控** | 全局视角扫描所有 Hermes 进程（gateway/worker/cron/CLI），实时显示每个 Agent 的状态：🟢工作中 / 🟠空闲 / ⚪离线 |
| 💬 **会话监控** | 跨所有 Profile 的活跃会话列表，每条显示：Profile/标题/来源/模型/消息数/工具调用数/活跃状态/进度阶段（初始→进行中→深入→收尾） |
| 📋 **Kanban 看板** | 6 列看板（triage/todo/ready/running/blocked/done），每列显示任务卡片，来自 `~/.hermes/kanban.db` |
| 🕸️ **Agent 拓扑图** | SVG 力导向图，节点=Agent/任务，边=委派/分配关系 |
| 📅 **协作时间线** | Kanban 事件 + Delegate 事件合并，按时间倒序 |
| 👷 **活跃 Worker** | 当前正在运行的 Kanban Worker（Task ID/Assignee/PID/启动时间/心跳） |
| 📖 **协作机制指南** | delegate_task vs Kanban 对比表 + 状态流转图 + 通信等级 L0-L3 |

**8 个视图**：协作仪表盘 · Agent 活动监控 · Kanban 看板 · Agent 拓扑图 · 协作时间线 · 活跃 Worker · 会话监控 · 协作机制指南

### 🌓 双主题

- **黑色主题**（默认）：深色背景，适合长时间使用
- **白色主题**：浅色背景，适合明亮环境
- 侧边栏标题栏 🌙/☀️ 一键切换，选择持久化到 localStorage

---

## ⚙️ 4 条设计原则

| 原则 | 含义 |
|---|---|
| 🔒 **只读旁路** | 永远不修改 Hermes 数据。任何写操作都会被拒绝。观测台崩溃不影响 Agent 正常运行 |
| 📸 **真实数据** | 不用任何样表/假数据/占位符。所有数字、时间线、谱系都来自真实的 `~/.hermes/**` |
| ⚡ **秒级响应** | 首屏加载 < 1s。慢采集器走后台缓存，端点缓存 10-60 秒不等 |
| 🧩 **零构建部署** | 后端一个 `python main.py` 起服务，前端单文件 HTML，无需 npm/webpack |

## 🚀 典型使用场景

**进化观测**：

- 🕐 **每日回顾** — 打开进化时间线，看今天/本周新增了哪些记忆、创建/修补了哪些技能
- 🔍 **异常追查** — 发现 Agent 行为变化，直接在谱系树里定位是哪一版 patch 引入的
- 📊 **额度监控** — MEMORY.md/USER.md 使用率仪表盘，逼近上限时提前预警
- 🧹 **审查决策** — Curator 归档/合并了哪些？依据是什么？不满意时回滚
- ✋ **拦截可疑** — 提示注入、密钥泄漏等异常写入进入审批队列，手动放行/拒绝

**协作观测**：

- 🤖 **Agent 状态总览** — 一眼看到所有 Agent 谁在工作、谁空闲、谁离线
- 💬 **会话进度** — 每个 Agent 当前有几个活跃会话？每个会话进展到什么阶段？
- 📋 **看板监控** — Kanban 任务分布在哪些状态？有没有卡在 blocked 的？
- 🕸️ **委派关系** — Agent 之间的委派和任务分配关系一目了然
- 👷 **Worker 健康** — 活跃 Worker 的 PID、心跳、运行时间

**开发者 / 研究者**：

- 📈 **进化速度可测量** — 每个技能从 v1.0 到当前版本经历了几次 patch/GEPA 优化，分数从多少涨到多少
- 🧬 **GEPA Pareto 前沿可视化** — 多目标优化的候选技能分布一目了然
- 🔀 **跨 profile 混排** — 同时运行多个 Agent profile 时，事件汇总到一条时间线
- 🌳 **谱系溯源** — 定位某个技能是"哪次会话里 Agent 自己创建的"，可点击跳回原始 session
- 🔄 **schema drift 探测** — Hermes 内部数据 schema 变化自动检测

## 📐 三层架构

1. **采集**：11 个只读采集器扫真实 Hermes 数据源（`~/.hermes/**`），永不修改
2. **织谱系**：把 memory 修改、skill 创建/patch、curator 归档、checkpoint 快照、Kanban 事件、delegate 事件等按时间/技能/profile 织成时间线和版本树
3. **呈现**：单文件 SPA 前端，21 个视图（13 进化 + 8 协作），含真实版本 Diff 展开、双主题切换

---

## 快速开始

### 1. 装

```bash
git clone https://github.com/luoxiangcai/hermes_observatory.git
cd hermes_observatory

# 用 uv（推荐）或 python -m venv
uv venv --seed .venv
.venv/bin/pip install -r requirements.txt
```

### 2. 起

```bash
.venv/bin/python backend/main.py
# 打开 http://127.0.0.1:9120/
```

或用 systemd user service（Linux/WSL 推荐，见 [部署](#部署)）。

### 3. 装 Plugin Hook（可选，但强烈建议）

Hook 负责把 `memory` / `skill_manage` / `skill_view` 调用**实时**记录成事件，让"进化时间线"和"谱系树"有真实数据。

```bash
# my-profile 是你的 Hermes profile 名，改成实际的（未开启 profile 时用 default）
PROFILE=my-profile

# 用软链方便就地开发（改代码即生效）
mkdir -p ~/.hermes/profiles/$PROFILE/plugins/
ln -sf "$(pwd)/plugins/hermes-observatory-hook" \
       ~/.hermes/profiles/$PROFILE/plugins/

# 启用
hermes plugins enable hermes-observatory-hook
```

> Hook 走 Hermes 的 `pre_tool` / `post_tool` / `on_session_*` 钩子，**下次新会话生效**——当前会话不会追溯。

## 项目结构

```
hermes_observatory/
├── README.md            · 你正在看
├── LICENSE              · MIT
├── CHANGELOG.md         · 变更日志
├── requirements.txt     · Python 依赖
├── Makefile             · install / run / test / dev
│
├── backend/             · FastAPI 后端
│   ├── main.py          · 单文件入口 · 35 个 API 路由 · WebSocket · 静态挂载
│   ├── config.py        · 端口/host/Hermes 路径解析 · 多 Profile 路由
│   ├── schema_registry.py · Schema 版本 + drift 探测
│   ├── narrative_generator.py · 进化叙事生成
│   └── collectors/      · 11 个只读采集器
│       ├── base.py      · BaseCollector 抽象类
│       ├── memory.py    · MEMORY.md / USER.md
│       ├── skills.py    · SKILL.md + .usage.json
│       ├── curator.py   · curator/*.jsonl
│       ├── gepa.py      · GEPA metrics
│       ├── pending.py   · 待审批写入
│       ├── events.py    · evolution-events.jsonl（支持跨 profile 混排）
│       ├── state_db.py  · SQLite / FTS5
│       ├── checkpoints.py · SKILL.md 快照 + diff
│       ├── kanban.py    · kanban.db 多 Agent 看板
│       ├── delegate.py  · delegate_task 委派日志
│       └── agent_activity.py · 全局 Agent 进程+会话监控
│
├── frontend/
│   └── index.html       · 2400+ 行单文件 SPA，零构建，21 视图，双主题
│
├── plugins/
│   └── hermes-observatory-hook/
│       ├── plugin.yaml
│       └── handler.py   · pre_tool 快照 + post_tool 事件采集
│
├── tests/               · 17 用例，全部通过
└── docs/
    ├── 设计文档.md      · 设计文档（定位、四判据、变化探测、视图）
    ├── 落地实施文档.md  · 落地文档（API、采集器接口、部署）
    └── demo.html        · 在线演示页面（含进化+协作+双主题）
```

## 数据模型

**从不修改 Hermes 数据**。观测台读这些位置：

| 采集器 | 读什么 | 说明 |
|---|---|---|
| `memory` | `<home>/memories/MEMORY.md`、`USER.md` | 段落解析 + 用量统计 |
| `skills` | `<home>/skills/**/SKILL.md`、`.usage.json` | 用 PyYAML 解析 frontmatter |
| `curator` | `<home>/logs/curator/*.jsonl` | 每次 curator run 一条 |
| `gepa` | `<home>/gepa/**` | 分数、Pareto |
| `pending` | `<home>/pending/*` | 待用户审批的写入 |
| `events` | `<home>/logs/evolution-events.jsonl` | 由 Plugin Hook 追加 |
| `state_db` | `<home>/state.db` (SQLite) | 会话/turn 元数据 |
| `checkpoints` | `<home>/skills/.checkpoints/<name>/*.md` | patch 前的 SKILL.md 快照 |
| `kanban` | `~/.hermes/kanban.db` (SQLite) | 多 Agent 任务看板（全局共享） |
| `delegate` | `<home>/logs/agent.log` + `state.db` | delegate_task 委派事件 |
| `agent_activity` | `psutil` + 所有 profile 的 `state.db` + PID 文件 | 全局进程+会话监控 |

`<home>` = 当前 profile 的家目录。default profile 在 `~/.hermes`；其他 profile 在 `~/.hermes/profiles/<name>/`。

**协作观测台是全局的**——不绑定单个 Profile，扫描整个 `~/.hermes/` 目录树。

## 配置

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `OBS_HOST` | `127.0.0.1` | 监听地址 |
| `OBS_PORT` | `9120` | 监听端口 |
| `HERMES_HOME` | `~/.hermes` | Hermes 数据根（也可指向 `~/.hermes/profiles/<name>`） |
| `HERMES_DASHBOARD_URL` | `http://127.0.0.1:9119` | Hermes Dashboard（用于 `/api/status` 和 drift 检测） |
| `OBS_COLLECT_INTERVAL` | `60` | 采集间隔（秒） |
| `OBS_DRIFT_INTERVAL` | `3600` | Drift 检测间隔（秒） |

## 部署

### systemd user service（Linux/WSL，推荐）

```ini
# ~/.config/systemd/user/hermes-observatory.service
[Unit]
Description=Hermes Observatory
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/path/to/hermes_observatory/backend
ExecStart=%h/path/to/hermes_observatory/.venv/bin/python main.py
Restart=on-failure
RestartSec=5
StandardOutput=append:%h/path/to/hermes_observatory/logs/observatory-systemd.log
StandardError=append:%h/path/to/hermes_observatory/logs/observatory-systemd.log

[Install]
WantedBy=default.target
```

启用：

```bash
systemctl --user daemon-reload
systemctl --user enable --now hermes-observatory
loginctl enable-linger $USER   # WSL / 无桌面登录场景
```

## 测试

```bash
.venv/bin/pytest tests/ -q
# 17 passed
```

## 开发

```bash
# 前后端一体，改代码后热重载
.venv/bin/uvicorn backend.main:app --reload --host 127.0.0.1 --port 9120
```

- 后端：`backend/main.py` 是单一入口，改 collectors 或 API 端点后 uvicorn 自动 reload
- 前端：`frontend/index.html` 单文件 SPA，改完 Ctrl+F5 强刷即可
- 测试：加新采集器时同步在 `tests/test_registry.py` 增加验证

## 已知限制

- **Hermes 私有钩子 API**：`plugins/hermes-observatory-hook/` 依赖 Hermes 的 `register_hook("pre_tool", ...)` API。Hermes 若换 API 需要调整 handler。
- **跨 profile 混排**：进化观测默认 `all_profiles=true` 合并所有 profile 事件。想按 profile 过滤，可在前端切换 profile pill。协作观测台本身就是全局的。
- **中文文档**：核心文档目前是中文。欢迎英文 PR。
- **无 auth**：默认绑 `127.0.0.1`，只能本机访问。若要对外暴露，前面加反向代理 + auth。

## 技术栈

- **后端**：Python 3.10+ · FastAPI · uvicorn · httpx · PyYAML · psutil
- **前端**：纯 HTML/CSS/JavaScript · 无构建 · 无框架 · 双主题
- **测试**：pytest · pytest-asyncio

## 贡献

欢迎 issue / PR。提交前请：

1. 跑 `pytest tests/`，17 用例全过
2. 新采集器同步加降级测试（数据源缺失时返回 `status: "unavailable"` 而非崩）
3. 前端改动 Ctrl+F5 手工验一遍

## 许可

[MIT](LICENSE) © 2026 luoxiangcai
