# 模块 B · 记忆业务引擎 —— 开发任务书

> **目录**：`backend/engine/`
> **开发人员**：1人

---

## 实现状态（2026-08-11）

> **赛题状态纠偏（2026-09-03）**：下列“已完成”仅表示适配代码和记忆引擎模块
> 已实现，不表示 H-02/H-03 通过。系统 Vector Engine 生产接线是 P0 未完成项；
> Embedding 需用最终版本在 V11 重新形成真实调用证据。
> 团队批准的 Agent 路线同时重新打开 ingest 契约：增加 `CONVERSATION` Connector，
> 扩展 `TOOL_RESULT` 运行来源，并对接 Module E 生命周期。该工作未实现前保持 🔴。

### 🔴 已批准的 Agent 接入任务

- B-A1：定义 `CONVERSATION` raw schema（user/assistant、session_id、turn_id、时间和 scope）。
- B-A2：扩展 `TOOL_RESULT` schema（run_id、tool_call_id、工具名、审批状态和来源）。
- B-A3：清洗、质量、敏感检测、偏好/知识抽取支持上述来源并保留 evidence 追溯。
- B-A4：与 C/E 完成契约测试；禁止用现有 `TOOL_RESULT` 类型伪装普通对话。

- ✅ **已完成并集成**：`ingest/`、`knowledge/`、`conflict/`、`security/`、`preference/`
  全部 Service 与测试；引擎已切换到 foundation core 契约（core 模型 / ULID ID /
  仓储语义 / 偏好版本化），并经 SQLite 全链路集成测试验证。
- ✅ **已完成**：`kylin/` 真实麒麟 SDK 适配——`embedding.py`（coreai/embedding）、
  `vector.py`（vector-engine-client）、`cpp/` pybind11 绑定源码与构建脚本；另有
  Debian 可移植特征哈希向量器作为明确的软件降级路径。
- 🟡 **麒麟 SDK 绑定已本机构建成功**（2026-08-24，`backend/engine/kylin/cpp/` pybind11
  编译导入通过）；麒麟环境 AI 运行时 / 向量引擎在线后的真实端到端调用仍待验证。
- 🟡 **OCR（kysdk-ocr / libkyocr）已接入**（2026-08-24）：pybind11 绑定
  `_kylin_ocr` + `engine/kylin/ocr.py` 适配层 + REST `POST /memory/ocr`
  （auto/kylin/portable 三档，无 SDK 环境返回 OCR_UNAVAILABLE）。
- 🔴 **向量数据库硬门槛未通过**：当前检索由 foundation/retrieval 的 SQLite INT8
  扫描承担；`engine/kylin/vector.py` 已完成集合装载与 insert/upsert/delete/search
  生命周期封装和契约测试，但尚未注入生产链。必须让系统 Vector Engine 实际承担
  生产建库、写入、删除和查询，并在 V11 严格画像中验证。
- ⬜ **离线文本生成**（AI SDK 9.5.1）：当前麒麟 apt 源未提供对应开发包，需在
  带该 SDK 的目标环境接入（持续缺口，不作为发布阻塞）。
- 测试：21 项全绿（麒麟 V11 真机与 foundation 联合 pytest 377 passed）；
  无麒麟 SDK 环境可使用生产 `portable` 路径；`tests/fakes.py` 仅用于隔离单元测试。
- 打包：整包 .deb 以源码随包安装引擎（`/usr/lib/pixiu/backend/engine`），
  麒麟 SDK 绑定在目标机构建后提供正式语义能力；无绑定时核心链路保持降级可用。

> 下文的文件清单为任务定义与优先级；已实现项以"实现状态"为准。

---

## 开工要求（本地环境准备）

开始开发前，**必须先补齐仓库内的官方麒麟 SDK submodule**：

```bash
git submodule update --init --recursive
```

- `third_party/kylin-coreai-embedding` —— 文本向量化 SDK（C API，`libkysdk-coreai-embedding`）
- `third_party/libkysdk-vector-engine-client` —— 向量数据库客户端（C++/gRPC）

未补齐 submodule 时，`kylin/` 相关代码无法引用 SDK 头文件，pybind11 绑定
（`backend/engine/kylin/cpp/`）无法构建，请勿跳过此步骤。

> ✅ 下文各阶段文件清单均已实现（以"实现状态"为准），保留作为实现明细参考。

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
| `kylin/embedding.py` | ★★★ | 麒麟 coreai/embedding 封装 + Debian 可移植向量器 + 能力选择 |
| `kylin/cpp/` | ★★★ | pybind11 绑定源码 + CMake 构建（SDK 以 third_party submodule 纳入） |
| `kylin/vector.py` | ★★ | 麒麟向量数据库客户端生命周期封装（含安全的 ID 删除接口） |

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
| `tests/test_sqlite_integration.py` | 引擎 × SQLite 全链路集成测试 |
| `tests/test_vector_client.py` | Vector Engine Python 适配器公共生命周期契约测试 |

默认生产配置优先调用真实麒麟 SDK，SDK 缺失时使用可移植软件向量器；严格
`kylin` 模式会抛出 `KylinSDKUnavailableError`。测试桩仅用于隔离单元测试。
