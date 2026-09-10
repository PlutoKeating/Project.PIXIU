# 记忆业务引擎开发记录

## 当前状态

正式版本为 0.1.12。偏好提取、账单更正、版本检查、知识合并、来源保留和安全遗忘已接入。

测试结果及后续验收项统一见[发布记录](../../../docs/RELEASE_0_1_10_COMPLETION_PLAN.md)。

## 工作范围

源码位于 `backend/engine/`，设计见[模块架构](ARCHITECTURE.md)。修改遵循根目录 AGENTS.md、公共 API 和已批准的目录结构。

## 验证入口

```bash
python3 -m pytest -q backend/engine/tests
```

提交时同步接口、依赖、构建配置和对应文档，记录实际执行的测试结果。
