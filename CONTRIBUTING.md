# 贡献指南

感谢你有兴趣改进 Hermes 进化观测台！本文档帮你从零到发出第一个 PR。

## 5 分钟 setup

```bash
git clone https://github.com/luoxiangcai/hermes_evolution-observatory.git
cd hermes_evolution-observatory

# 创建虚拟环境（用 uv 或 python -m venv 都行）
uv venv --seed .venv
.venv/bin/pip install -e ".[dev]"

# 跑测试确认环境好
.venv/bin/pytest tests/ -v
# 应该看到 17 passed

# 启动本地开发服务器（自动 reload）
.venv/bin/uvicorn backend.main:app --reload --host 127.0.0.1 --port 9120
```

浏览器打开 <http://127.0.0.1:9120/> 就能看到界面。

## 目录导览

- `backend/main.py` — FastAPI 单一入口，所有 API 路由在这
- `backend/collectors/` — 8 个只读采集器；加新数据源在这加
- `backend/schema_registry.py` — Schema 版本 + drift 探测
- `frontend/index.html` — 单文件 SPA，零构建，改完 Ctrl+F5 强刷
- `plugins/evolution-observatory-hook/` — Hermes 插件（写事件到 jsonl）
- `tests/` — pytest 用例，加新采集器时同步加降级测试

## 开发工作流

### 加新的数据采集器

1. 在 `backend/collectors/` 里新建 `mycollector.py`，继承 `BaseCollector`
2. 实现 `collect()` 方法，返回 `CollectorResult`
3. 数据源缺失时**返回** `status="unavailable"` — **绝不 raise**（Hermes 主流程不能被观测台干扰）
4. 在 `backend/collectors/__init__.py` 里 `register("mycollector", MyCollector)`
5. 在 `tests/test_registry.py` 里加断言：注册表包含 `"mycollector"`
6. 在 `tests/test_degraded_mode.py` 里加降级测试：数据源缺失时不崩

### 加新的 API 端点

1. 在 `backend/main.py` 里加 `@app.get("/api/xxx")`
2. 慢端点用 `@ttl_cache(seconds)` 装饰（现有的 drift=60s / narrative=20s / lineage=20s / overview=10s）
3. 前端 `frontend/index.html` 里对应视图接 API
4. 数据源不可用时**前端**用 `unavailableHTML(msg)` helper 渲染友好占位

### 前端改动

- `frontend/index.html` 是**单文件 SPA**，1800+ 行。这是**有意的架构决定**（零构建、单文件部署）
- helper 函数集：`loadingHTML() / errorHTML() / emptyHTML() / unavailableHTML() / fileActionsHTML()` — 保持完整定义后再使用
- `PAGE_LOADERS` + `PAGE_LOADED` 处理懒加载，切换 profile 时会 `PAGE_LOADED.clear()`

## 测试规约

- 每个采集器都要有**降级测试**：数据源不存在 → 返回 unavailable，而非 KeyError/FileNotFoundError
- 加新 API 端点时**至少加一个 smoke test**（能跑通、返回 200）
- `pytest tests/ -q` 必须全绿才能 push；CI 会阻挡红叉的 PR

## 代码风格

- Python：`ruff format` + `ruff check`（配置在 `pyproject.toml`）
- 缩进 4 空格，行宽 100
- Docstring 用中文；对外 API/命令保持英文
- 变量名、函数名保持英文

## 提交 PR

1. Fork 仓库、创建分支：`git checkout -b feature/xxx`
2. 改代码 + 跑测试 + `git commit`（commit message 中英文都行，清晰即可）
3. Push 到 fork、在 GitHub 上开 PR
4. CI 会自动跑测试，红叉需要修好才能合并
5. 在 PR 描述里说明**改了什么 + 为什么 + 如何测试**

## Issue 模板

**Bug 报告**：请包含

- 复现步骤（越具体越好，最好是可以 copy-paste 的命令）
- 期望行为 vs 实际行为
- Hermes 版本、Python 版本、OS
- 相关日志（`logs/observatory-systemd.log` 或 uvicorn 输出）

**Feature 请求**：请说明

- 使用场景（你想解决什么问题）
- 期望的行为
- 现有方案的不足

## 已知约束（不接受的 PR 方向）

- **前端拆分**：拆成 React/Vue 等前端项目会打破"零构建、单文件部署"这一核心设计
- **修改 Hermes 数据**：观测台永远只读，任何写入 `~/.hermes/**` 的 PR 会被拒
- **同步阻塞 API**：所有 API 必须 <200ms 响应；慢数据源用后台采集器 + 缓存
- **依赖膨胀**：新增依赖需要在 PR 里说明必要性（能用标准库就用标准库）

## 遇到问题

- 环境搭建问题 → 开个 issue，我尽快回
- 想聊聊架构和方向 → 也开 issue，直接讨论

MIT License · 欢迎 fork
