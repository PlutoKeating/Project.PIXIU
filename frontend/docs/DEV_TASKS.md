# 桌面客户端开发记录

## 当前状态

正式版本为 0.1.12。统一桌面、左侧分类、回答来源、动效总开关、后台整理审批和进度已接入。

测试结果及后续验收项统一见[发布记录](../../docs/RELEASE_0_1_10_COMPLETION_PLAN.md)。

## 工作范围

源码位于 `frontend/`，设计见[模块架构](ARCHITECTURE.md)。修改遵循根目录 AGENTS.md、公共 API 和已批准的目录结构。

## 验证入口

```bash
cmake -S frontend -B /tmp/pixiu-frontend -DPIXIU_MANAGEMENT_TESTS=ON
```

提交时同步接口、依赖、构建配置和对应文档，记录实际执行的测试结果。
