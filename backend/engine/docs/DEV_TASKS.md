# 模块 B · 记忆业务引擎 —— 开发任务书

> **目录**：`backend/engine/`
> **开发人员**：1人

---

## 第一阶段：核心管线

### ingest/ —— 多源数据接入

| 文件 | 优先级 | 说明 |
|------|--------|------|
| `ingest/__init__.py` | ★★★ | 导出 `IngestionService` |
| `ingest/cleaner.py` | ★★★ | 去噪、去重（内容 hash 指纹）、缺失字段处理 |
| `ingest/normalizer.py` | ★★★ | 格式标准化 + 实体规范化（别名词典/规则归一） |
| `ingest/quality.py` | ★★★ | `quality_score` 计算（字段完整度+来源置信度）+ Schema 校验 |
| `ingest/connectors/__init__.py` | ★★ | Connector 基类 |
| `ingest/connectors/tool_result.py` | ★★ | 工具执行结果接入适配 |
| `ingest/connectors/user_behavior.py` | ★★ | 用户行为数据接入适配 |
| `ingest/connectors/manual_config.py` | ★★ | 手动配置信息接入适配 |
| `ingest/connectors/ocr.py` | ★★ | OCR 结果接入适配（含实体预提取） |

### knowledge/ —— 知识结构化

| 文件 | 优先级 | 说明 |
|------|--------|------|
| `knowledge/__init__.py` | ★★★ | 导出 `KnowledgeService` |
| `knowledge/structurer.py` | ★★★ | 按 kind（FACT/WORKFLOW/CASE/TEMPLATE）结构化 KnowledgeItem |
| `knowledge/graph.py` | ★★★ | 实体抽取 + BELONG_TO 等关系构建 |
| `knowledge/embed_writer.py` | ★★★ | 调 KylinEmbedding → INT8 量化 → 写入向量索引 |

### kylin/ —— KylinSDK 适配

| 文件 | 优先级 | 说明 |
|------|--------|------|
| `kylin/__init__.py` | ★★★ | 导出 `KylinTextEmbedding` |
| `kylin/embedding.py` | ★★★ | C++ pybind11 封装（麒麟 coreai/embedding C 接口） |
| `kylin/mock_embedding.py` | ★★★ | MockEmbedding 降级实现（返回固定维度随机向量） |

---

## 第二阶段：辅助功能

### preference/ —— 偏好捕捉

| 文件 | 优先级 | 说明 |
|------|--------|------|
| `preference/__init__.py` | ★★ | 导出 `PreferenceService` |
| `preference/extractor.py` | ★★ | 三类偏好提取（规则信号 + 离线文本生成抽取键值对） |
| `preference/versioning.py` | ★★ | 版本化（写 history 快照，version+1）+ 回溯接口 |
| `preference/adapter.py` | ★★ | 跨场景适配（按 scope + 场景标签解析生效版本） |

### conflict/ —— 冲突仲裁

| 文件 | 优先级 | 说明 |
|------|--------|------|
| `conflict/__init__.py` | ★★ | 导出 `ConflictService` |
| `conflict/arbiter.py` | ★★ | 矛盾检测（同实体同字段比较）+ 裁决（NEW_WINS/MERGE/MANUAL）+ 审计（ConflictRecord） |

### security/ —— 安全与遗忘

| 文件 | 优先级 | 说明 |
|------|--------|------|
| `security/__init__.py` | ★★ | 导出 `SecurityService` |
| `security/detector.py` | ★★ | 敏感信息识别（正则：身份证/银行卡/手机号）+ sensitivity 评分 |
| `security/forget.py` | ★★ | 自然语言遗忘（解析指令→匹配定位→级联清理→tombstone） |

---

## 测试

| 文件 | 说明 |
|------|------|
| `tests/test_ingest.py` | 多源接入管线测试（含噪声/缺失/重复数据） |
| `tests/test_preference.py` | 三类偏好提取+版本化+回溯测试 |
| `tests/test_knowledge.py` | 四类知识结构化+建图+嵌写入测试 |
| `tests/test_conflict.py` | 矛盾检测+裁决+审计测试 |
| `tests/test_security.py` | 敏感识别+遗忘精确性+级联清理测试 |
| `tests/test_kylin.py` | MockEmbedding 端到端测试 |

所有测试须在 `PIXIU_EMBEDDING=mock` 环境下可独立运行。
