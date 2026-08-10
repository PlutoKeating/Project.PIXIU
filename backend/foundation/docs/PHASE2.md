# Module C · Phase 2 记忆流转验收报告

> 日期：2026-08-09  
> 范围：`backend/foundation/flow/`、必要的 Foundation 存储/API 接入、测试与模块文档。  
> 环境：Anaconda `pixiu`，Python 3.10.20。

## 1. 已完成

- 新增 `memory_contexts` 基础表与 v3 迁移，持久化层级、payload、scope、状态、TTL 和
  沉淀后的 `knowledge_id`。
- 新增 `ctx_` ULID；短期默认 TTL 30 分钟，中期默认 TTL 7 天，允许调用方显式覆盖。
- `FlowService.remember` 保存短/中期上下文；`promote` 支持短期或中期批量沉淀，复用
  Module B 的 `IngestionService → KnowledgeService` 真实链路。
- promote 在产生副作用前整体校验 ID、scope、来源层级和状态；重复请求返回已有
  `knowledge_id`，不会重复生成长期记忆。
- `demote` 将 ACTIVE 长期知识复制为短/中期快照，原长期知识不删除、不改状态。
- TTL sweep 只处理到期的 ACTIVE 上下文，保留审计行并清空 payload；已 PROMOTED
  上下文取消 TTL，不会被 sweep 清理。
- `/memory/flow/promote` 已按根目录 API 契约返回 `promoted_count`、`knowledge_ids`、
  `latency_ms`，并将领域错误映射为 404/400。

## 2. 验证结果

```text
D:\Anaconda\envs\pixiu\python.exe -m pytest \
  backend/foundation/tests backend/engine/tests -q -ra

268 passed, 1 warning in 4.51s
```

- Foundation：247 项。
- Engine：21 项。
- 唯一警告是既有 Starlette `TestClient` 与 httpx 的弃用提示，本阶段未升级依赖，避免
  扩大变更范围。

## 3. 边界与后续

- 未修改 `backend/engine/`，跨模块组装仍只发生在 `backend/foundation/api/di.py`。
- 未实现 sync、eval 或 D-Bus；`/sync/*` 仍是占位端点。
- Windows 环境不具备银河麒麟原生 embedding 扩展；测试仍通过显式注入测试桩验证
  业务链路，生产配置没有 mock fallback。
- 根目录文档存在阶段状态滞后，但按 Module C 文件归属规则未在本阶段修改；应由项目
  负责人统一更新跨模块计划与验收状态。
