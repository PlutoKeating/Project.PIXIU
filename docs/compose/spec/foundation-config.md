---
feature: foundation-config
status: delivered
updated: 2026-07-29
branch: feature/foundation-bootstrap
commits: c36d0f3..3fa106a
---

# core/config.py — 配置单例

> 2026-09-06 代码复核：当前 Settings 与 backend/.env.example 覆盖 API、XDG 数据、同步及 SDK 选择；Embedding/Vector 均支持 auto/kylin/portable，旧“仅 kylin”约束已被可移植基线取代。
> 下文实施步骤、旧接口草图和测试数字保留作阶段历史，不作为当前操作手册；当前契约见 docs/API.md，发布见 docs/DELIVERY_PLAN.md。

> ⚠️ **历史交付记录**：本文记录 2026-07 的阶段性交付；2026-08-07 起 `PIXIU_EMBEDDING`
> 仅支持 `kylin`（无 mock）。最新状态以 `docs/DEVELOPMENT_PLAN.md` 为准。

## Report

**What was built** — `core/config.py` 集中管理所有环境变量配置。`Settings` 单例提供 6 个类型安全的只读属性（`db_path`, `api_host`, `api_port`, `embedding`, `log_level`, `data_dir`），变量名与 `backend/.env.example` 完全一致。端口校验 1-65535、embedding 仅支持 `kylin`（真实麒麟 SDK，无 mock 降级）、日志级别限于 DEBUG/INFO/WARNING/ERROR，不合法时抛明确 `ValueError`。同时更新 `api/di.py` 和 `core/logger.py`，移除裸 `os.getenv` 调用，统一通过 `settings` 访问配置。

**Verification** — `pytest backend/tests/test_config.py -v`: 21/21 passed (0.12s)。覆盖默认值、环境变量读取、非法值拒绝（embedding/port/log_level）、边界值（端口 1/65535）、辅助函数单元测试。

**Journey log**
- 辅助函数必须定义在 `Settings` 类之前，否则模块级 `settings = Settings()` 执行时 `_env_str` 未定义
- 使用 `mock.patch.dict(os.environ, {}, clear=True)` 隔离测试环境变量，比 `monkeypatch.setenv` 更可靠（清空现有变量）
- 纯 Python `Settings` 类而非 pydantic-settings，避免与 models.py 形成循环依赖

## [S1] Problem

当前环境变量分散在 `di.py`（`PIXIU_DB_PATH`）和 `logger.py`（`PIXIU_LOG_LEVEL`）中以 `os.getenv` 裸调，无校验、无集中入口、无默认值文档。需要一份单一的配置模块，将 `backend/.env.example` 中定义的 6 个变量集中读取、校验、并提供类型安全的配置对象。

## [S2] Design

### S2.1 config.py

单一文件 `backend/foundation/core/config.py`，提供 `Settings` 类（非 Pydantic — 纯 Python，避免循环依赖，models.py 已经依赖 pydantic）。

**变量名** — 与 `backend/.env.example` 完全一致：

| 变量名 | 类型 | 默认值 | 校验 |
|--------|------|--------|------|
| `PIXIU_DB_PATH` | `str` | `"./pixiu.db"` | 非空字符串 |
| `PIXIU_API_HOST` | `str` | `"127.0.0.1"` | 合法 hostname/IP |
| `PIXIU_API_PORT` | `int` | `8765` | 1-65535 整数，拒绝 0 |
| `PIXIU_EMBEDDING` | `str` | `"kylin"` | 枚举：仅 `"kylin"`（无 mock 降级），其余拒绝 |
| `PIXIU_LOG_LEVEL` | `str` | `"INFO"` | 枚举：`DEBUG/INFO/WARNING/ERROR` |
| `PIXIU_DATA_DIR` | `str` | `"./data"` | 非空字符串 |

**关键实现细节**：
- 模块级单例 `settings = Settings()`，导入即初始化
- `os.getenv` 读取，不存在时回退默认值
- 端口用 `int()` 转换，`ValueError` 时抛明确错误
- Embedding 后端不合法时抛 `ValueError` 并列出合法选项
- 不做路径实存检查（数据库可能尚不存在，由 schema.init_db 负责创建）
- 不向路径注入用户目录或系统目录

### S2.2 tests/test_config.py

测试文件 `backend/tests/test_config.py`，覆盖以下 4 个场景：

1. **默认值** — 不设环境变量时，`PIXIU_API_PORT` 为 `8765`
2. **embedding=kylin 读取** — 设置 `PIXIU_EMBEDDING=kylin`，`settings.embedding` 返回 `"kylin"`
3. **非法 embedding 拒绝** — 设置 `PIXIU_EMBEDDING=openai`，初始化应抛 `ValueError`
4. **临时数据库路径可配置** — 设置 `PIXIU_DB_PATH=/tmp/test.db`，`settings.db_path` 应返回该路径

额外覆盖：
5. 非法端口（0 / 70000 / "abc"）应抛 `ValueError`
6. 合法端口边界值（1, 65535）正常通过

**测试实现要点**：
- 使用 `monkeypatch.setenv` 设置环境变量
- 每个测试独立：patch `os.environ` 或使用 `mock.patch.dict`，避免相互污染
- `Settings.__init__` 每次调用读取当前环境变量，因此测试中需确保隔离

### S2.3 更新已有引用

- `api/di.py`：不再直接 `os.getenv("PIXIU_DB_PATH", ...)`，改为 `from ..core.config import settings; settings.db_path`
- `core/logger.py`：`get_logger()` 使用 `settings.log_level` 而非硬编码 `"INFO"`

## [S3] Out of Scope

- 不做路径是否存在检查
- 不做端口是否被占用检查
- 不做热重载（配置只在启动时读取一次）
- 不引入 pydantic-settings（过度引入依赖）

## Tasks

- [x] T1: 实现 core/config.py — Settings 类，6 个属性，含校验逻辑 (covers: S2.1)
- [x] T2: 更新 api/di.py — 用 settings.db_path 替换 os.getenv (covers: S2.3)
- [x] T3: 更新 core/logger.py — 用 settings.log_level 替换硬编码值 (covers: S2.3)
- [x] T4: 实现 tests/test_config.py — 21 个测试用例，含默认值、kylin、非法拒绝（含 mock 拒绝）、路径可配 (covers: S2.2)
- [x] T5: 运行 pytest 确认全部通过 (covers: S2.2)
