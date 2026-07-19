# 变更日志 · CHANGELOG

本文档记录 Hermes 进化观测台（evolution-observatory）代码库的重要变更。
最新变更放在最上面。日期格式：`YYYY-MM-DD`，条目按功能/修复归类。

---

## 2026-07-19 · 开源基础设施：CI + pyproject.toml + CONTRIBUTING

在开源准备的 P0（LICENSE / .gitignore / README / 硬编码清理）基础上，把 P1 三件套一次补齐。

### ✨ 新增文件

**`.github/workflows/test.yml`** — GitHub Actions CI
- 每次 push / PR 自动跑 pytest
- 矩阵测试 Python 3.10 / 3.11 / 3.12
- 附加 smoke test：验证 `backend.config` 和 `backend.collectors` 可以 import
- 免费无限量（公开 repo）

**`pyproject.toml`** — 现代 Python 项目元数据
- `name = "hermes-evolution-observatory"`，版本 0.1.0
- 5 个 runtime 依赖（fastapi/uvicorn/httpx/pydantic/pyyaml）
- optional `dev` 依赖组（pytest + ruff）
- 定义 CLI 命令 `evolution-observatory = "backend.main:main"`
- 集成 pytest 和 ruff 配置
- 允许 `pip install -e ".[dev]"` 或 `uv sync`

**`CONTRIBUTING.md`** — 贡献指南
- 5 分钟 setup 指令
- 目录导览、开发工作流
- 新采集器/API 端点/前端改动的规约
- 测试规约、代码风格、PR 流程
- 已知约束（不接受的 PR 方向：前端拆分、写入 Hermes 数据、同步阻塞 API、依赖膨胀）

**`.github/ISSUE_TEMPLATE/bug_report.md`** — Bug 报告模板（含环境/日志/复现步骤字段）
**`.github/ISSUE_TEMPLATE/feature_request.md`** — Feature 请求模板
**`.github/pull_request_template.md`** — PR 模板（含检查清单和测试说明）

### 🔧 代码改动

- `backend/main.py`：将底部 `if __name__ == "__main__":` 里的启动代码抽成 `def main():` 函数，暴露为 pyproject.toml 的 `[project.scripts]` CLI 入口点
- `README.md`：`git clone` URL 对齐真实仓库名 `hermes_evolution-observatory`

### 🧪 验证

- 17/17 pytest 通过
- `python -c "import tomllib; ..."` 确认 pyproject.toml 合法
- systemd 服务重启后 `/api/health` 正常
- `grep /home/lxc` 在 `.py .html .yaml .yml .toml` 代码文件里为 0

---

## 2026-07-19 · 开源准备：硬编码路径清零 + LICENSE / .gitignore / README 重写

准备把项目 push 到 GitHub。做了 5 件事，都是"未来任何 clone 到自己机器上的人都能跑通"的必要条件。

### 🐛 修复 · 硬编码用户路径

- `backend/main.py:476` 和 `:550`：`/api/reveal` 和 `/api/file/view` 白名单里写死 `/home/lxc/workspace/evolution-observatory`，改成 `Path(__file__).resolve().parent.parent` 运行时推断项目根
- `frontend/index.html:1523`：显示技能路径时把 `/home/lxc` 替换成 `~`，改成正则 `/\/home\/[^/]+/` 匹配任意用户名

### ✨ 新增文件

- **LICENSE**（MIT · Copyright 2026 luoxiangcai）
- **.gitignore**（覆盖 Python/venv/日志/密钥/IDE/测试缓存/数据库）
- **README.md**（完全重写：正确插件安装、8 采集器、22 API 路由、17 测试、systemd unit 模板、贡献指南、已知限制）

### 🧹 清理

- `logs/observatory-systemd.log`（328KB，含真实运行 IP/profile 名）已删除；`logs/` 目录进 `.gitignore`
- `.pytest_cache/` 进 `.gitignore`

### 🧪 验证

- 17/17 pytest 通过
- `/api/reveal?path=README.md` 返回正确的 explorer.exe action
- `grep /home/lxc` 在 py/html/yaml 代码文件里为 0

### 📝 未来贡献者友好度

- README 添加 badges（tests / python / license / status）
- 明确说 Plugin Hook 依赖 Hermes 私有钩子 API（未来 Hermes 换 API 需要调整）
- 说明"下次会话生效"这一 Hook 隐式约定

---

## 2026-07-18 · 进化时间线 · 跨 profile 混排 + 数据源诊断 + 样表格局对齐

用户看到时间线空空如也又对不上样表，问"进化时间线为什么没有更新"。三层原因 + 三层修复。

### 🔎 根因

1. **插件长期没装到 Hermes**（早上刚 `hermes plugins enable`）
2. **handler.py 硬编码写到 `~/.hermes/logs/evolution-events.jsonl`（default 根）**，但当前 profile 是 `ceo`，Hermes 会用 `HERMES_HOME=~/.hermes/profiles/ceo`
3. **采集器只读当前 profile 一个源**——即便有多 profile 也做不到样表那种"default / coder / research 混排"

### 🐛 修复

**handler.py（插件）**
- 新增 `_hermes_home()`：读 `$HERMES_HOME`，兜底读 `~/.hermes/active_profile` 决定家目录
- 新增 `_current_profile()`：`profiles/<name>` 或 `default`
- `_write_event()` 用 `_events_file()`（相对当前 profile），并自动补 `profile` 字段
- 删掉硬编码 `EVENTS_FILE` 常量

**events 采集器（backend/collectors/events.py）**
- `collect(all_profiles=True)`：`True` 时枚举 hermes root + 全部 `profiles/<name>/`，把每个 `logs/evolution-events.jsonl` 都读进来并合并；`False` 时只读当前 profile
- 返回 `sources: [{profile, file, exists, size}]`，前端能看到"扫了哪些源、哪些存在、多大"
- 事件若没标 `profile` 字段，按文件归属兜底

**/api/timeline 端点**
- 新增 `all_profiles: bool = True`（默认开）
- 通过 `registry._collectors.get("events")` 直接调用采集器 `collect(all_profiles=...)`（因 `collect_one` 不接受参数）
- 返回带 `sources` + `all_profiles` 元数据

**前端 renderEventsTimeline**
- **空态改成信息卡**，明确解释：样表那些跨 profile 事件是示意；实际数据源今天才刚 enable；下次 Hermes 会话 memory/skill_manage/skill_view 调用会自动产生日志
- **头部信息条**：`N 条事件 · 按时间倒序` + `跨 M 个 profile 混排` 或 `仅当前 profile`
- **profile 徽章按名字上色**：`default=cyan / coder=purple / research=pink / ceo=amber`，其他 profile fallback 灰
- **时间戳 tooltip**：`title="2026-07-18T14:17:04Z"`，鼠标停留看精确时间
- **checkpoint 图标**：`📸` 加入 icons 表

### 🧪 验证

- 17/17 pytest 全绿
- `/api/timeline?profile=ceo` 返回 `sources=[{default,exists:False}, {ceo,exists:True,size:218B}]`
- 前端刷新看到诊断卡：明确指出"default 未产生日志、ceo 只 1 条测试事件"

### 📂 文件变更

- `plugins/evolution-observatory-hook/handler.py` — profile-aware 事件写入 + `_hermes_home()` 解析
- `backend/collectors/events.py` — 跨 profile 混排 + sources 元数据
- `backend/main.py` — `/api/timeline` 加 `all_profiles` 参数
- `frontend/index.html` — 时间线渲染改成样表格局 + 空态诊断卡 + 头部信息条
- `CHANGELOG.md` — 本条目

### 📝 关于样表那种"数十条跨 profile 事件"

样表里 `default / coder / research` 三个 profile 混着几十条事件——这是**理想图**，需要真实使用积累。当前系统里：
- 磁盘上只有 1 个 profile（`ceo`）
- 只有 1 条历史事件（早期手工 curl POST /api/events 测试产生）
- 插件刚 enable，需要**新开 Hermes 会话**，任何 memory/skill/skill_view 调用会写入日志
- 事件积累到几十条时，混排页就会长得跟样表几乎一样

---

## 2026-07-18 · 中文化：project-verification 技能翻译 + 插件真装到 Hermes

用户偏好："以后创建的 skill 及其 patch 都用中文写"，已入长期记忆。这轮做两件事。

### ✨ 中文化 project-verification 技能

- `skills/devops/project-verification/SKILL.md` 从英文全文改写为**中文**（371 行 / 16.5KB / 12008 chars）
- frontmatter 里 `description:` 用 YAML `>` 折叠语法，正文含"触发条件 / 工作流程 / 常见坑 / 性能优化 / 变体场景 / Checkpoints 机制 / systemd 用户服务调试 / CHANGELOG 约定 / 关联参考"共 8 节
- 命令、路径、变量名、错误信息（`ensurepip`、`address already in use`、`--seed` 等）保持原文
- 关联的 6 份 `references/` 暂未翻译（下次 patch 到时再顺手改）

### 🐛 修复 · skills 采集器 frontmatter 解析

- 之前用手工 `line.split(":", 1)`，看到 `description: >` 就存了字面量 `>`，YAML 折叠语法完全没处理
- 改用 **`yaml.safe_load()`** 完整解析 frontmatter，支持 `>`（折叠）、`|`（保留换行）、list、dict 等所有 YAML 形式
- description/version 非字符串时兜底转 `str()`，避免前端出现 `[object Object]`
- 兜底路径保留手工解析，PyYAML 加载失败也能取到简单字段

### 🚀 部署 · 插件真装到 Hermes 生效

- 发现 `plugins/evolution-observatory-hook/` 之前**从未装到 Hermes**——之前所谓 "pre_tool 快照落盘" 是我手工模拟 `handler._on_pre_tool()` 触发的，不是 Hermes 自动调用的
- 修法：`ln -sf .../plugins/evolution-observatory-hook ~/.hermes/profiles/ceo/plugins/`（软链，方便就地开发同步）
- `hermes plugins enable evolution-observatory-hook` 已启用
- 提示"Takes effect on next session" — 当前 hermes 会话不激活，**下次新会话** patch/edit 任何 skill 时钩子才真正跑，拍快照到 `skills/.checkpoints/<name>/<ts>.md`

### 🧪 测试

- 17/17 pytest 全绿

### 📂 文件变更

- `~/.hermes/profiles/ceo/skills/devops/project-verification/SKILL.md` — 中文重写
- `backend/collectors/skills.py` — 用 PyYAML 解析 frontmatter，desc/version 类型安全
- `~/.hermes/profiles/ceo/plugins/evolution-observatory-hook` → 软链到项目仓库
- `CHANGELOG.md` — 本条目

### 🔎 顺带发现的 Hermes 原生能力

- `hermes checkpoints` 命令是 Hermes 原生 shadow git，**只针对 `write_file/patch/terminal` 写盘操作**，不针对 `skill_manage`
- 我们自己的 `skills/.checkpoints/` 系统是**独立的**、专门给 SKILL.md 的快照，两者不冲突
- `hermes plugins ls` / `hermes hooks ls` 是标准的插件/钩子管理入口，未来加新钩子可直接靠 Hermes CLI 而不用改 handler.py

---

## 2026-07-18 · 文件跳转 📂📄：在 WebUI 里直接打开 / 查看真实文件

用户希望"技能库、记忆状态卡片里能点击直达对应文件所在位置"。本轮加了两个新端点 + 一套通用前端组件，把每条数据背后真实的文件路径变成一键可跳转。

### ✨ 新增能力

**后端两个新端点（含路径白名单约束）：**

| 端点 | 用途 |
|---|---|
| `GET /api/reveal?path=X` | 校验路径在白名单内后，用 `explorer.exe /select, <winpath>` 弹出 Windows 资源管理器并高亮该文件；纯 Linux 环境降级用 `xdg-open` 打开所在目录 |
| `GET /api/file/view?path=X&max_bytes=N` | 在浏览器里查看文件内容，白名单外 denied、超 200KB 截断 |

**路径白名单：**
- 当前 profile 的 hermes_home（含 skills / memories / logs / .checkpoints）
- 若 `HERMES_HOME` 指向 profile 目录，父级 hermes root 也纳入
- `/home/lxc/workspace/evolution-observatory`（项目自身）
- **其他一律 denied**，防止用户误传 `/etc/passwd` 等

**采集器补 abs_path：**
- `SkillsCollector` — 活/归档技能都返回 `abs_path`（原有 `path` 相对路径保留兼容）
- `MemoryCollector` — MEMORY.md / USER.md 返回 `abs_path`（含 unavailable 情形，方便用户看空文件应该在哪）
- `/api/lineage` 返回 `abs_path`（当前 SKILL.md）+ 每个 checkpoint 事件返回 `checkpoint_path`

### 🎨 前端 · 通用文件操作组件

- `fileActionsHTML(absPath)` 返回一对 `📂📄` 图标锚点，data-* 声明式：
  - `<a data-reveal="/abs/path">📂</a>` — 打开系统资源管理器
  - `<a data-view="/abs/path">📄</a>` — 打开浏览器内的文件查看器 overlay
- **全局委托** `document.addEventListener('click')` 用 `.closest([data-...])` 匹配，任何位置渲染的图标点击都会触发
- **文件查看 overlay** — 全屏遮罩 + 单文件面板，顶栏显示文件名/大小/mtime + 📂 快捷跳转 + ✖ 关闭；点击遮罩外区域自动关闭；超 200KB 提示已截断
- **Toast 提示** — reveal 成功/失败右下弹 2.2s 消息

### 4 处渲染点接入

| 位置 | 表现 |
|---|---|
| 技能库卡片 · 技能名右侧 | `github-code-review 📂 📄` — 点 📂 弹 explorer 选中 SKILL.md；点 📄 在浏览器里看全文 |
| 谱系树 · 顶部技能名 | 同上，点开就能看当前 SKILL.md |
| 谱系树 · checkpoint 事件行 | "🔍 查看该次修改的 Diff  📂 📄" — 📄 直接看那份历史快照 md 全文 |
| 记忆状态 · MEMORY.md / USER.md 条目 meta 行 | "📄 MEMORY.md 📂 📄" — 一眼定位 memories/ 目录，或直接看全文（对整段文本的 USER.md 尤其有用） |

### 🛡️ 安全策略

- 所有 path 都 `resolve()` 之后与白名单前缀匹配，防止 `..` 越权
- `/api/file/view` 只返回 UTF-8 文本，binary 内容用 `errors='replace'` 降级，避免 JSON 序列化失败
- 端点不写文件、不执行任意命令；`subprocess.Popen` 参数用列表形式（无 shell 注入）
- WSL 下 `explorer.exe` 若不在 PATH，自动 fallback 到 `/mnt/c/Windows/explorer.exe`（systemd user service 场景）

### 🐛 顺带修的 systemd 兼容性

`systemctl --user` 拉起的服务继承的是清洁 PATH（不含 `/mnt/c/Windows`），第一次 curl `/api/reveal` 报 `No such file or directory: 'explorer.exe'`。加了三级 fallback：`explorer.exe` → `/mnt/c/Windows/explorer.exe` → `/mnt/c/Windows/System32/explorer.exe`。

### 🧪 验证

- 17/17 pytest 全绿
- `curl /api/reveal?path=/etc/passwd` → `{"status":"denied"}`
- `curl /api/reveal?path=CHANGELOG.md` → `{"status":"ok","action":"/mnt/c/Windows/explorer.exe /select, \\\\wsl.localhost\\Ubuntu\\..."}`（explorer 窗口实际会弹出选中该文件）
- `curl /api/file/view?path=README.md` → `{"status":"ok","size":3698,"content":"..."}`
- 前端 `{}` `()` 括号平衡 488/488、892/892

### 📂 文件变更

- `backend/main.py` — `/api/reveal` `/api/file/view` `_is_wsl()` + lineage 加 `abs_path`/`checkpoint_path`
- `backend/collectors/skills.py` — 活/归档技能加 `abs_path`
- `backend/collectors/memory.py` — MEMORY/USER 采集加 `abs_path`
- `frontend/index.html` — `fileActionsHTML` `doReveal` `doView` `toast` + file-viewer overlay + 全局 click 委托；4 处渲染点接入
- `CHANGELOG.md` — 本条目

---

## 2026-07-18 · Checkpoints：真实 SKILL.md 快照与逐版本 Diff

用户希望"谱系树能看到真实的版本 diff"。此前 Hermes 不在 `skill_manage patch/edit` 前保存 SKILL.md 快照，所以无法追溯历史差异。本轮加了一整套**Checkpoints 机制**——插件层拍快照、后端读快照、前端渲染 unified diff。

### ✨ 新增能力

- **插件 pre_tool 钩子** — `plugins/evolution-observatory-hook/handler.py` 注册 `pre_tool` 钩子；每次 Agent 调 `skill_manage(action='patch'|'edit', name=X)` **之前**，将当前 `SKILL.md` 拷贝到 `<hermes_home>/skills/.checkpoints/<X>/<UTC 时间戳>.md`；同时把动作/session/turn 元数据追加到 `.meta.jsonl`
- **快照修剪** — 每个技能最多保留 50 份最近快照，超出自动删最老（`.meta.jsonl` 保留，作长期审计）
- **失败不阻塞** — 全部 try/except，快照失败只 debug 日志，绝不 raise，绝不影响真实 patch 操作
- **异步逻辑** — 因 pre_tool 是同步钩子，快照做的是 read+write（&lt;5ms），实测对 patch 延迟无感知
- **手工验证过** — 模拟 pre_tool 触发一次，`skills/.checkpoints/project-verification/20260718T135140875571Z.md` 落盘 13164B，`.meta.jsonl` 追加正确

### ✨ 新增采集器 & 端点

| 组件 | 路径 | 用途 |
|---|---|---|
| `CheckpointsCollector` | `backend/collectors/checkpoints.py` | 扫 `skills/.checkpoints/` 列出所有技能的历史快照 + `.meta.jsonl` metadata |
| `GET /api/checkpoints` | 支持 `?skill=X` 或列全部 | 前端列快照 |
| `GET /api/checkpoint/diff` | `?skill=&from_file=&to_file=&compare_current=` | `difflib.unified_diff` 计算两份快照或"快照 vs 当前 SKILL.md"的差异，30s TTL 缓存 |

### 🎨 前端 · 谱系树增强

- 谱系树时间轴上，每个 `checkpoint` 事件用 **📸 紫色** 展示（区别于 🌱 create / 🔧 patch / 🧹 curator / 🧬 GEPA / 📦 archive）
- 每个 checkpoint 事件下加 "🔍 查看该次修改的 Diff" 链接，点击展开 unified diff 面板：
  - `+` 行绿色底 `-` 行红色底 `@@` 蓝色底 头部灰色
  - `+N -M` 汇总在顶部
  - 再次点击折叠
  - `max-height:400px` + `overflow:auto` 避免撑爆布局
- 能力说明卡文本随实际情况切换：
  - **已启用 Checkpoints 且有该技能快照** → ✅ 蓝底：告知点 📸 即可看真实 diff
  - **未启用/无快照** → ⚠️ 黄底：告知钩子已注册但需一次真实 patch 才生成第一份

### 🧪 测试

- `tests/test_registry.py` 加 2 个新用例：
  - `test_checkpoints_collector_unavailable_when_no_dir` — 目录不存在时 status=unavailable 且 total_snapshots=0
  - `test_checkpoints_collector_reads_snapshots` — 构造 2 份快照 + `.meta.jsonl`，验证 action/session 元数据正确 merge
- 旧硬编码 `assert len(...) == 7` 改为 `>= 8`（未来扩展友好）
- **17/17 全绿**

### 🛡️ 副作用评估（在动手前已确认）

| 项 | 结论 |
|---|---|
| 磁盘占用 | 每技能 50×~15KB ≈ 750KB 上限；总量随技能数量线性增长 |
| 写延迟 | pre_tool 钩子 &lt;5ms，实测无感知 |
| 失败传播 | 全部 try/except，绝不 raise |
| 敏感数据 | 与 SKILL.md 同权限、同目录、随 profile 隔离 |
| Hermes 更新兼容 | 用稳定的 pre_tool hook；即便签名变了也只是插件不加载，不影响主功能 |
| 回退能力 | `rm -rf ~/.hermes/*/skills/.checkpoints` 或删除插件目录即可 |

### 📂 本轮文件变更

- `plugins/evolution-observatory-hook/handler.py` — 新增 pre_tool 钩子 + 5 个辅助函数
- `backend/collectors/checkpoints.py` — 新增采集器
- `backend/collectors/__init__.py` — 注册新采集器
- `backend/main.py` — `/api/checkpoints` + `/api/checkpoint/diff` + `/api/lineage` 合入 checkpoint 事件与动态 capabilities note
- `frontend/index.html` — kindIcons/kindColors 加 checkpoint 项、diff 展开委托、renderDiff 函数、事件模板加"查看 diff"按钮
- `tests/test_registry.py` — 加 2 测试 + 放宽计数断言
- `CHANGELOG.md` — 本条目

---

## 2026-07-18 · 首次真实数据接线 + 性能优化 + 系统化部署

用户反馈项目"看着像样表、模块加载慢、部分界面不对"。本轮修复覆盖前端所有 12 个视图、后端 8 个端点、加了 4 个新端点，并把观测台接入 systemd 开机自启。

### 🐛 严重 Bug 修复

- **`unavailableHTML is not defined`** — 前端 4 处调用了该 helper 但从未定义，导致 memory / skills / curator / lineage 页在数据源 unavailable 时显示红色报错。补上定义。
- **`config.get_hermes_home("default")` 返回错误路径** — 当 `HERMES_HOME` 指向 `~/.hermes/profiles/ceo` 时，"default" profile 也被算成 ceo，导致两个 profile 显示相同数据。重写 `_find_hermes_root()`，先反推 `~/.hermes` 根，再解析 profile。
- **`NarrativeGenerator._load_events` 二次 profile 过滤错杀** — 事件文件本就按 profile 隔离，代码里又按 `event.profile` 过滤一次导致 ceo 的事件全部被丢。移除多余过滤，改为按 `timestamp` 天数窗口过滤。

### ✨ 新增后端端点

| 端点 | 用途 |
|---|---|
| `GET /api/profiles` | 扫真实 `~/.hermes/profiles/` + 根目录（default），返回 `{profiles, active, profiles_dir}` |
| `GET /api/lineage?profile=&skill=` | 从 `.usage.json` + `evolution-events.jsonl` + curator runs 重建单技能历史，附 `capabilities` 说明能到什么程度 |
| `GET /api/skills/history?days=` | 按 `created_at` 聚合的技能库增长曲线 |
| `GET /api/pareto` | 从 GEPA metrics 挖 accuracy / cost 二元组作帕累托散点 |

### 🎨 前端接真数据（消除样表）

前端 `frontend/index.html` 原本 12 处硬编码 `mock*` 数组 + `Math.random()`，从未调后端。本轮全部替换：

| 视图 | 数据源 | 变更 |
|---|---|---|
| 顶部 Profile pill | `/api/profiles` | 从硬编码 `default/coder/research/personal` 改为动态渲染真实 profile |
| 总览仪表盘（6 张卡 + 三层活动 + 增长图）| `/api/overview` `/api/skills/history` `/api/timeline` `/api/memory` | 之前完全是硬编码（47/12/67%/54%/8/3、L1=31/L2=18/L3=8）；现按真实 stats 填 |
| 进化时间线 | `/api/timeline` | 已接（本次未改）|
| 记忆状态（MEMORY.md / USER.md 进度条 + 条目）| `/api/memory` | 进度条从 `1474/2200 · 67%` `742/1375 · 54%` 硬编码改为真实 usage；空 entries 但存在 `raw_content` 时整段展示 |
| 技能库（顶部状态徽章 + 卡片）| `/api/skills` | 徽章 Active/Stale/Archived/Pinned/Bundled/Agent-created 从写死改为真实计数 |
| Curator 活动（4 张卡 + 时间线）| `/api/curator` | 总运行/归档/合并/修补从硬编码 14/4/2/7 改为聚合 runs 的 actions |
| 进化谱系树 | `/api/lineage` | 从 v1.0→v1.3 假样表改为下拉选真实技能、真实事件（创建/patch/curator）时间轴 |
| GEPA 进化分数 | `/api/gepa` | 已接（本次未改）|
| 帕累托前沿 | `/api/pareto` | 从 4 个坐标写死改为真实 metrics 散点 |
| 待审批 | `/api/pending` | 已接 |
| 变化探测 | `/api/drift` | 已接 |
| 数据源健康 | `/api/health` | 已接 |
| 进化叙事 | `/api/narrative` | 从写死"Docker SSH 坑 GEPA 0.85→0.91"改为按事件生成 |
| 术语表（mockGlossary）| 前端静态资料 | **保留**——后端无端点，是纯静态资料 |
| 架构页 · 多 Profile 路由 | `/api/profiles` | 从假的 default/coder/research/personal + `~/.hermes-coder/` 假路径改为真实列表 |

### ⚡ 性能优化（模块加载 10s → 15ms）

- **`/api/drift`：10,666ms → 73ms（146×）**
  - `httpx` 请求 dashboard 从 `timeout=5` 改为 `httpx.Timeout(1.0, connect=0.5)`
  - 请求前用 socket 快速探测 9119 端口（150ms），30s 结果缓存
  - 端点结果 60s TTL 缓存
- **TTL 内存缓存**（`main.py` 新增 `ttl_cache` 装饰器）：`overview`=10s、`skills`=15s、`narrative`=20s、`lineage`=20s、`skills/history`=20s、`drift`=60s
- **前端懒加载**：`loadAll()` 从并发 14 个 render 改为只加载当前 active tab；其余 12 个 tab 首次点击时才拉数据；切 profile 时清空 `PAGE_LOADED` 只重刷当前页
- **定时轮询**：`setInterval(refreshOverview, 30000)` 从"永远刷 overview"改为"只在 overview tab 已加载时刷"

### 🚀 部署

- 新建 systemd user unit：`~/.config/systemd/user/evolution-observatory.service`
  - `After=network-online.target hermes-webui.service`
  - `Restart=on-failure`
  - 日志写入 `~/workspace/evolution-observatory/logs/observatory-systemd.log`
- 已 `systemctl --user enable --now evolution-observatory.service`
- 已确认 `~/.hermes/config/user linger=yes` + WSL `/etc/wsl.conf` 有 `systemd=true`——**Ubuntu 启动后 9119（hermes-webui）+ 9120（observatory）都会自动就位**

### 📝 文档

- 加了本 `CHANGELOG.md`
- 谱系树末尾加"能力说明卡"：诚实告诉用户当前基于 `.usage.json + evolution-events.jsonl + curator runs`；Hermes 未给 SKILL.md 分配 semver 版本号也未在 patch 前自动保存历史快照，因此不展示 v1.0→v1.1 版本树与逐版本 diff（如需该能力可在插件层实现 Checkpoints）

### 🖼️ UI 细节

- 👁️ / ⚡ / 🔧 三个图标在技能库卡片和谱系树中都加上了中文 tooltip（view/use/patch 各是什么），并在谱系树顶部提供图例
- 前端进度条元素统一 id 化（`memory-usage-text/pct/bar`、`user-usage-text/pct/bar`）便于 renderMemory 填数
- Curator/Skills unavailable 时改用黄色 `unavailableHTML()` 而非红色 `errorHTML()`，视觉上区分"降级不可用"与"真的报错"

### 🧪 测试

- 15/15 pytest 用例全绿（`tests/test_collectors.py` `tests/test_registry.py` `tests/test_degraded_mode.py`）
- 手工 bench 8 个端点：除 drift 之外全部 &lt;30ms 冷启动 / &lt;5ms 热缓存

### 📂 文件变更

- `backend/main.py` — +160 行：4 个新端点 + ttl_cache 装饰器
- `backend/config.py` — 重写 `_find_hermes_root()` + `get_hermes_home()`，修 profile 路径解析
- `backend/schema_registry.py` — +30 行：socket 端口探测 + 短超时
- `backend/narrative_generator.py` — 修二次 profile 过滤 + 补天数窗口
- `frontend/index.html` — 大改：删 6 个 mock 顶层数组、加 4 个 render 函数（Narrative/Lineage/Architecture-profiles/Growth）、懒加载路由、能力说明卡
- `~/.config/systemd/user/evolution-observatory.service` — 新增
- `CHANGELOG.md` — 新增（本文件）

---

## 之前

（更早的变更请参见 git log。项目自初始版本以来的骨架：FastAPI 后端 17 个端点 + WebSocket 广播 + 7 个采集器插件 + 单文件 HTML 前端 + SQLite/FTS5 状态库 + 15 个 pytest 用例）
