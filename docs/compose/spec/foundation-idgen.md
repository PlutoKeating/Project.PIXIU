---
feature: foundation-idgen-tests
status: delivered
updated: 2026-07-29
branch: feature/foundation-bootstrap
commits: 3fa106a..0b6f480
---

# core/idgen.py — 测试与清理

> 2026-09-06 代码复核：当前生成器位于 backend/foundation/core/idgen.py，测试位于 backend/foundation/tests/test_idgen.py；长度为各前缀长度加 26，不统一为 30。
> 下文实施步骤、旧接口草图和测试数字保留作阶段历史，不作为当前操作手册；当前契约见 docs/API.md，发布见 docs/DELIVERY_PLAN.md。

> ⚠️ **历史交付记录**：本文记录 2026-07 的阶段性交付，内容与当前代码一致。

## Report

**What was built** — `core/idgen.py` 清理了未使用的 `import hashlib`，补充 14 个专有测试用例。测试覆盖三大维度的正确性：

**Verification** — `pytest backend/tests/test_idgen.py -v`: 14/14 passed (0.18s)。覆盖前缀、唯一性（单生成器 1000 次 + 跨 8 生成器 800 个混合）、类型、长度一致性、字符集合法性。

**Journey log**
- `pref_` 和 `sync_` 是 5 字符前缀（非 4），ID 总长 = len(prefix) + 26，初始测试漏算导致 3 个 failure，修正后全部通过
- 跨生成器唯一性测试使用前缀不同天然保证不冲突，但仍通过集合去重验证

## Report

## [S1] Problem

`core/idgen.py` 已在第一阶实现但未经专门测试。代码中有未使用的 `import hashlib`，全局状态变量 `_LAST_TS`/`_LAST_RAND` 在快速连续调用时防碰撞但测试中可能互相污染。需要补充测试并清理无用的 import。

## [S2] Design

### S2.1 代码改动（仅清理）

- 删除 `import hashlib`（无使用）
- 其余代码不变

### S2.2 tests/test_idgen.py — 3 组测试

#### 组 1：前缀正确

8 个生成器各自返回以正确前缀开头（含下划线）的字符串：

| 函数 | 期望前缀 |
|------|---------|
| `gen_evidence_id()` | `evd_` |
| `gen_knowledge_id()` | `knw_` |
| `gen_pref_id()` | `pref_` |
| `gen_conflict_id()` | `cfl_` |
| `gen_device_id()` | `dev_` |
| `gen_sync_op_id()` | `sync_` |
| `gen_entity_id()` | `ent_` |
| `gen_request_id()` | `req_` |

每个测试：调用生成器 → `assert result.startswith("evd_")`

#### 组 2：连续生成不会重复

每个生成器调用 1000 次 → 收集 ID → `assert len(set(ids)) == 1000`（朴素集合去重检查唯一性）。

同时测试：
- 跨生成器不重复：从 8 个生成器各取 100 个 ID → 总数 800 → 放入同一集合 → 应无冲突
- ID 长度固定为 30（4 前缀 + `_` + 26 ULID）

#### 组 3：返回值是字符串

每个生成器调用一次 → `assert isinstance(result, str)` → `assert not result.isdigit()`（非纯数字）

### S2.3 不修改生成器实现

当前 ULID 算法（时间戳 50bit + 随机 80bit → Crockford Base32 编码）工作正常，不做算法改动。全局变量在快速循环 1000 次内有 `_LAST_RAND + 1` 兜底，唯一性足够。

## [S3] Out of Scope

- 不引入 `python-ulid` 第三方库
- 不做跨进程/跨机器唯一性测试（已在算法层面保证）
- 不做排序性验证（ULID 时间戳前缀天然保证）

## Tasks

- [x] T1: 清理 idgen.py — 删除 `import hashlib` (covers: S2.1)
- [x] T2: 实现 tests/test_idgen.py — 前缀正确 (covers: S2.2 组1)
- [x] T3: 实现 tests/test_idgen.py — 连续生成不重复 (covers: S2.2 组2)
- [x] T4: 实现 tests/test_idgen.py — 返回值是字符串 (covers: S2.2 组3)
- [x] T5: 运行 pytest 确认全部通过 (covers: S2.2)
