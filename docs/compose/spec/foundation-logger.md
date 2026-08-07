---
feature: foundation-logger
status: delivered
updated: 2026-07-29
branch: feature/foundation-bootstrap
commits: 52694a2..3ac58c6
---

# core/logger.py — 结构化日志与安全过滤

> ⚠️ **历史交付记录**：本文记录 2026-07 的阶段性交付，内容与当前代码一致。

## Report

**What was built** — 重写 `core/logger.py`，提供两种 logger 获取方式（普通 `get_logger` 返回 `[-]` request_id，`get_request_logger` 注入具体 request_id）、`SafeFormatter`（处理缺失 request_id 回退）、`SensitiveFilter`（6 条正则规则过滤密码/token/secret/api_key/私钥块/卡号）。全栈 stdlib `logging`，零外部依赖。

**Verification** — `pytest backend/tests/ -v`: 46/46 passed (0.21s)。logger 专项 11 个测试覆盖：普通 logger 格式、请求 logger request_id 注入、7 种敏感字段过滤（password/token/secret/api_key/私钥/卡号/干净消息透传）、多字段同时过滤。

**Journey log**
- JSON 格式 `"password": "abc123"` 中的值被 `\S+` 整段捕获（含引号），替换后无残留引号——测试断言需精确匹配替换结果
- `get_logger` 返回 `LoggerAdapter` 而非裸 `Logger`，测试中需通过 `logging.getLogger(name)` 获取底层 logger 来添加 handler

## Report

## [S1] Problem

当前 `logger.py` 缺少两个关键能力：
1. **request_id 追踪** — 检索链路跨多个模块（路由→检索→融合→重排→组装），无法关联同一请求的日志
2. **敏感信息泄露** — 无任何过滤机制，日志中可能输出密码、token、私钥等

## [S2] Design

### S2.1 日志格式

```text
2026-07-29T14:30:05.123 | INFO    | foundation.api.http_app | [req_01K...] | POST /memory/write -> 200
```

五个字段：时间(毫秒) | 级别(7字符) | 模块名 | [request_id] | 消息

无 request_id 时显示 `[-]`（通过普通 `get_logger` 获取的 logger）。

### S2.2 两个 Logger 获取方式

```python
from backend.foundation.core.logger import get_logger, get_request_logger

log = get_logger(__name__)
# → 2026-07-29T... | INFO    | foundation.api.di | [-] | db connected

req_log = get_request_logger(__name__, request_id="req_01KYS...")
# → 2026-07-29T... | INFO    | foundation.retrieval.bm25 | [req_01KYS...] | query=...
```

实现：`get_request_logger` 返回 `logging.LoggerAdapter`，在 `extra` 中注入 `request_id`。普通 `get_logger` 不变。

### S2.3 敏感信息过滤（`SensitiveFilter`）

在 `logging.Filter.filter(record)` 中对 `record.msg` 做正则替换，禁止输出的内容：

| 模式 | 替换结果 |
|------|---------|
| `password=...` 或 `password": "..."` | `password=***` / `password": "***"` |
| `token=...` 或 `token": "..."` | `token=***` / `token": "***"` |
| `-----BEGIN ... PRIVATE KEY-----` 块 | `[REDACTED PRIVATE KEY]` |
| `secret=...` 或 `secret": "..."` | `secret=***` / `secret": "***"` |
| `api_key=...` | `api_key=***` |
| 16 位连续数字（信用卡号）| `[REDACTED CARD]` |

**重要**：只对 `record.msg`（字符串）做过滤，不处理 `record.args`（结构化参数），避免性能问题。调用方应避免在 `args` 中传敏感数据后用 `%s` 格式化。

### S2.4 自定义 Formatter

`SafeFormatter(logging.Formatter)`：
- 格式化字符串中包含 `%(request_id)s`，若 `record` 无此属性则回退 `"-"`（通过重写 `format` 方法补全 record）
- 默认 datefmt 为 `%Y-%m-%dT%H:%M:%S`（毫秒通过 `%(asctime)s` 的 `,` 分隔实现）

### S2.5 测试（tests/test_logger.py）

4 组测试：

1. **普通 logger 输出正确** — `get_logger(__name__)` 创建的 logger，`log.info("hello")` 输出包含时间/级别/模块名/消息，request_id 为 `[-]`
2. **请求 logger 输出 request_id** — `get_request_logger(__name__, "req_test")` 输出 `[req_test]`
3. **敏感信息过滤** — `log.info('password=abc123')` 输出中密码被替换为 `***`
4. **私钥块过滤** — 包含 `-----BEGIN RSA PRIVATE KEY-----` 的消息被替换为 `[REDACTED PRIVATE KEY]`

测试方式：`logging.StreamHandler` 捕获到 `StringIO`，检查输出字符串内容。

## [S3] Out of Scope

- 不做 JSON 格式日志（当前保持纯文本）
- 不做日志轮转/文件输出（由外部工具或后续阶段控制）
- 不做分布式 trace ID（只用 request_id 关联单次请求）
- 不做 `record.args` 中的敏感数据检测

## Tasks

- [x] T1: 实现 `SafeFormatter` — 自定义 Formatter，处理缺失 `request_id` (covers: S2.1, S2.4)
- [x] T2: 实现 `SensitiveFilter` — 对 `record.msg` 中敏感字段做正则替换 (covers: S2.3)
- [x] T3: 实现 `get_request_logger` — LoggerAdapter 注入 request_id (covers: S2.2)
- [x] T4: 更新 `get_logger` — 注册 SafeFormatter + SensitiveFilter (covers: S2.1, S2.2)
- [x] T5: 实现 tests/test_logger.py — 11 个测试用例 (covers: S2.5)
- [x] T6: 运行 pytest 确认全部通过 (covers: S2.5)
