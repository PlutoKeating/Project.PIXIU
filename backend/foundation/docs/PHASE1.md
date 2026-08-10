# Module C · Phase 1 检索加固报告

> 日期：2026-08-09
>
> 分支：`feat/foundation`
>
> 状态：代码与本地回归完成；真实麒麟 SDK 性能验收待银河麒麟环境。

## 1. 完成内容

### 1.1 knowledge↔entity 持久化

- Schema 升级到 v2，新增 `knowledge_entities` 多对多关联表与实体侧索引
- 保存知识时，将显式 `entities` 与 relation 两端实体写入同一事务
- `get`、FTS、title search、`list_active` 统一回填实体名
- Graph 通道按实体稳定 ID 沿 `BELONG_TO` 一跳遍历，不再依赖 title/body 文本偶然命中
- 已验证 SQLite 连接关闭后重新打开，Graph 仍能召回关联知识

### 1.2 检索执行与上下文约束

- BM25、ANN、Graph 使用 `asyncio.gather` 并发执行
- `context_hint.scope` 从加权改为硬过滤，其他 scope 不进入融合结果
- `context_hint.time_range` 支持 `today`、`last_week`、`last_7_days`、
  `last_month`、`last_30_days`，以及带 `start/end` 的 UTC 时间区间
- 时间过滤优先使用结构化 body/date 或 items/date，缺失时回退 `KnowledgeItem.created_at`

### 1.3 结构化聚合

- 金额查询优先按 query 中明确出现的 `category` 筛选条目
- 未命中 category 时再匹配 `tag` / `vendor`，最后才回退全部有效金额条目
- 附录 A 混合食品与水电燃气清单返回 434.50 元，不再错误汇总整张清单

## 2. 验证结果

所有 Python 命令均使用 Conda `pixiu` 环境（Python 3.10.20）：

```bash
python -m pytest backend/foundation/tests/test_schema.py \
  backend/foundation/tests/test_knowledge_repository.py \
  backend/foundation/tests/test_entity_repository.py \
  backend/foundation/tests/test_retrieval.py -q -ra
# 64 passed, 1 warning

python -m pytest backend/foundation/tests backend/engine/tests -q -ra
# 252 passed, 1 warning
```

新增/强化的关键回归：

- v1 数据库升级到 v2
- knowledge↔entity 关联刷新与仓储重开回填
- 数据库关闭/重开后的 Graph 召回
- 三通道同时进入执行态
- scope 端到端隔离
- `last_month` 与显式时间区间过滤
- 附录 A 的 434.50 元聚合

唯一警告仍为 Starlette `TestClient` 对当前 httpx 集成方式的弃用提示。

## 3. 本地提交

- `4150082 feat(foundation/storage): persist knowledge entity links`
- `ae991d2 fix(foundation/retrieval): harden query isolation and aggregation`

## 4. 银河麒麟环境验收项

当前 Windows `pixiu` 环境没有 `_kylin_text_embedding` 原生扩展，调用生产
`get_embedder()` 会按设计抛出 `KylinSDKUnavailableError`，未启用 mock 降级。

因此以下指标必须在安装麒麟 embedding SDK、原生扩展与 AI 运行时的银河麒麟机器完成：

1. 正式 50 组家庭支出黄金集 top-1 召回率 ≥85%；
2. 真实 embedding 下 1000 次查询 P95 ≤500ms；
3. x86/ARM 目标机资源占用与兼容性记录。

这属于环境验收，不阻塞 Phase 1 的代码审查，但在最终交付前必须完成。
