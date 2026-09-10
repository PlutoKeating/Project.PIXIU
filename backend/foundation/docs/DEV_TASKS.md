# 后台基础设施开发记录

## 当前状态

正式版本为 0.1.12。公共 API、文档解码、持久审批、检索、同步和来源快照更新已接入。

测试结果及后续验收项统一见[发布记录](../../../docs/RELEASE_0_1_10_COMPLETION_PLAN.md)。

## 工作范围

源码位于 `backend/foundation/`，设计见[模块架构](ARCHITECTURE.md)。修改遵循根目录 AGENTS.md、公共 API 和已批准的目录结构。

## 验证入口

```bash
python3 -m pytest -q backend/foundation/tests
```

提交时同步接口、依赖、构建配置和对应文档，记录实际执行的测试结果。
