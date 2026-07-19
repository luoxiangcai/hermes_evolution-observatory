# Hermes 进化观测台 · Evolution Observatory

> 一个横切在所有 [Hermes Agent](https://hermes-agent.nousresearch.com) 进化机制之上的**只读观测层**。
> 采集进化事件 → 织成进化谱系 → 呈现进化叙事。

[![tests](https://img.shields.io/badge/tests-17%20passed-brightgreen)]()
[![python](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![license](https://img.shields.io/badge/license-MIT-green)]()
[![status](https://img.shields.io/badge/status-alpha-orange)]()

---

## 是什么

Hermes Agent 有多个进化机制：`memory`（长期记忆）、`skill_manage`（技能创建/修补）、`curator`（Skill 归档/合并）、`GEPA`（自演化）、`background_review`（后台复盘）、`Checkpoints`（快照）……

**这些机制各自都能跑，但过去没有统一的观测口**。这个项目做三件事：

1. **采集**：8 个只读采集器扫真实 Hermes 数据源（`~/.hermes/**`），永不修改
2. **织谱系**：把 memory 修改、skill 创建/patch、curator 归档、checkpoint 快照等事件按时间/技能/profile 织成时间线和版本树
3. **呈现**：单文件 SPA 前端，12 个视图，含真实版本 Diff 展开

## 截图

> 下图是实际运行中的界面（点击截图可放大看）。此外还有一份**带完整演示数据的交互原型** 👇

<div align="center">
  <a href="screenshots/demo.html">
    <img src="https://img.shields.io/badge/📱_在线演示-点击查看_demo.html-blue?style=for-the-badge" alt="在线演示">
  </a>
  <br>
  <sub>💡 下载后直接在浏览器打开，所有数据（47 个技能、8 次 GEPA 进化、3 条待审批等）都是预填充的演示数据</sub>
</div>

<br>

<!--
  🔧 使用说明：
  1. 打开 http://127.0.0.1:9120/ 用截图工具（Win+Shift+S）截几张关键页面
  2. 保存为 .png 放到本项目 screenshots/ 目录
  3. 修改下面的文件名、alt 文本和对应视图
-->

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

---

## 快速开始

### 1. 装

```bash
git clone https://github.com/luoxiangcai/hermes_evolution-observatory.git
cd hermes_evolution-observatory

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
# ceo 是你的 Hermes profile 名，改成实际的
PROFILE=ceo

# 用软链方便就地开发（改代码即生效）
mkdir -p ~/.hermes/profiles/$PROFILE/plugins/
ln -sf "$(pwd)/plugins/evolution-observatory-hook" \
       ~/.hermes/profiles/$PROFILE/plugins/

# 启用
hermes plugins enable evolution-observatory-hook
```

> Hook 走 Hermes 的 `pre_tool` / `post_tool` / `on_session_*` 钩子，**下次新会话生效**——当前会话不会追溯。

## 项目结构

```
evolution-observatory/
├── README.md            · 你正在看
├── LICENSE              · MIT
├── CHANGELOG.md         · 变更日志
├── requirements.txt     · Python 依赖
├── Makefile             · install / run / test / dev
│
├── backend/             · FastAPI 后端
│   ├── main.py          · 单文件入口 · 22 个 API 路由 · WebSocket · 静态挂载
│   ├── config.py        · 端口/host/Hermes 路径解析
│   ├── schema_registry.py · Schema 版本 + drift 探测
│   ├── narrative_generator.py · 进化叙事生成
│   └── collectors/      · 8 个只读采集器
│       ├── base.py      · BaseCollector 抽象类
│       ├── memory.py    · MEMORY.md / USER.md
│       ├── skills.py    · SKILL.md + .usage.json
│       ├── curator.py   · curator/*.jsonl
│       ├── gepa.py      · GEPA metrics
│       ├── pending.py   · 待审批写入
│       ├── events.py    · evolution-events.jsonl（支持跨 profile 混排）
│       ├── state_db.py  · SQLite / FTS5
│       └── checkpoints.py · SKILL.md 快照 + diff
│
├── frontend/
│   └── index.html       · 1800+ 行单文件 SPA，零构建，12 视图
│
├── plugins/
│   └── evolution-observatory-hook/
│       ├── plugin.yaml
│       └── handler.py   · pre_tool / post_tool 钩子
│
├── tests/               · 17 用例，全部通过
└── docs/
    ├── DESIGN.md        · 设计文档（定位、四判据、变化探测、视图）
    └── IMPLEMENTATION.md · 落地文档（API、采集器接口、部署）
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

`<home>` = 当前 profile 的家目录。default profile 在 `~/.hermes`；其他 profile 在 `~/.hermes/profiles/<name>/`。

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
# ~/.config/systemd/user/evolution-observatory.service
[Unit]
Description=Hermes Evolution Observatory
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/path/to/evolution-observatory/backend
ExecStart=%h/path/to/evolution-observatory/.venv/bin/python main.py
Restart=on-failure
RestartSec=5
StandardOutput=append:%h/path/to/evolution-observatory/logs/observatory-systemd.log
StandardError=append:%h/path/to/evolution-observatory/logs/observatory-systemd.log

[Install]
WantedBy=default.target
```

启用：

```bash
systemctl --user daemon-reload
systemctl --user enable --now evolution-observatory
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

- **Hermes 私有钩子 API**：`plugins/evolution-observatory-hook/` 依赖 Hermes 的 `register_hook("pre_tool", ...)` API。Hermes 若换 API 需要调整 handler。
- **跨 profile 混排**：观测台默认 `all_profiles=true` 合并所有 profile 事件。想按 profile 过滤，可在前端切换 profile pill。
- **中文文档**：核心文档目前是中文。欢迎英文 PR。
- **无 auth**：默认绑 `127.0.0.1`，只能本机访问。若要对外暴露，前面加反向代理 + auth。

## 技术栈

- **后端**：Python 3.10+ · FastAPI · uvicorn · httpx · PyYAML
- **前端**：纯 HTML/CSS/JavaScript · 无构建 · 无框架
- **测试**：pytest · pytest-asyncio

## 贡献

欢迎 issue / PR。提交前请：

1. 跑 `pytest tests/`，17 用例全过
2. 新采集器同步加降级测试（数据源缺失时返回 `status: "unavailable"` 而非崩）
3. 前端改动 Ctrl+F5 手工验一遍

## 许可

[MIT](LICENSE) © 2026 luoxiangcai
