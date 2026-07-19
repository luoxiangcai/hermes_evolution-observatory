## 改动说明

<!-- 一句话说清楚这个 PR 做了什么 -->

## 关联 Issue

<!-- 若有：Fixes #123 或 Related to #456 -->

## 改动类型

- [ ] Bug 修复
- [ ] 新功能
- [ ] 文档更新
- [ ] 重构（不改变外部行为）
- [ ] 性能优化
- [ ] 测试改进
- [ ] 其他：

## 检查清单

- [ ] `pytest tests/ -q` 全绿
- [ ] 新增采集器时，写了降级测试
- [ ] 新增 API 端点时，写了 smoke test
- [ ] 前端改动手工在浏览器验证过（Ctrl+F5）
- [ ] 若改了对外行为，更新了 README/CHANGELOG

## 如何测试

<!-- 告诉 reviewer 怎么验证你的改动。最好是 copy-paste 就能跑的命令 -->

```bash
# 例如：
.venv/bin/pytest tests/test_xxx.py -v
curl http://127.0.0.1:9120/api/新端点
```

## 截图（如涉及 UI）

<!-- 前端改动请附上前后对比截图 -->

## 附加说明

<!-- 有什么需要 reviewer 特别注意的？任何权衡取舍？ -->
