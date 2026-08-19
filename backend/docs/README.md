# 后端文档总览

> 后端（`backend/`）按架构维度拆分为**两个独立开发模块**，分属不同子目录。
> **严禁跨目录引用代码**，模块间仅通过 `foundation/core/` 中的抽象接口通信。

---

## 模块 B · 记忆业务引擎（`backend/engine/`）

Python 3.10 + C++（KylinSDK pybind11 封装）

| 子包 | 职责 |
|------|------|
| `ingest/` | 多源数据接入（4类 Connector → Cleaner → Normalizer → Quality） |
| `preference/` | 偏好捕捉（Extractor → Versioning → Adapter） |
| `knowledge/` | 知识结构化（Structurer → Graph → EmbedWriter） |
| `conflict/` | 冲突仲裁（Arbiter：检测→裁决→审计） |
| `security/` | 安全/遗忘（Detector + ForgetEngine） |
| `kylin/` | 麒麟 SDK 适配（coreai/embedding pybind11）+ Debian 软件降级 |

**文档**：
- [架构设计](engine/docs/ARCHITECTURE.md)
- [开发任务书](engine/docs/DEV_TASKS.md)
- [快速启动](engine/docs/QUICK_START.md)

## 模块 C · 后台基础设施（`backend/foundation/`）

Python 3.10 + SQLite + hnswlib

| 子包 | 职责 |
|------|------|
| `core/` | 共享契约（数据模型、Repository 接口、配置） |
| `api/` | API 网关（HTTP/WS/D-Bus） |
| `storage/` | SQLite 仓储实现（16 张表 + WAL + FTS5 + 向量，版本化迁移） |
| `retrieval/` | 混合检索（路由→BM25∥ANN∥Graph→融合→重排→组装） |
| `flow/` | 记忆流转（promote/demote + TTL） |
| `sync/` | P2P CRDT 同步（Gossip + 反熵 + TLS） |
| `eval/` | 评测框架 |

> **状态（2026-08-11）**：foundation Phase 0~7 全部完成（retrieval/flow/sync/eval/
> D-Bus + request_id 统一错误契约），12 个 REST 端点真实实现；引擎核心管线已
> 集成，麒麟 SDK 绑定待构建。全量测试：麒麟 V11 真机 pytest 377 passed。

**文档**：
- [架构设计](foundation/docs/ARCHITECTURE.md)
- [开发任务书](foundation/docs/DEV_TASKS.md)
- [快速启动](foundation/docs/QUICK_START.md)

## 快速索引

```bash
# 全部后端测试
cd backend
pip install -r requirements.txt
PIXIU_EMBEDDING=portable pytest engine/tests/ foundation/tests/ -v
```
