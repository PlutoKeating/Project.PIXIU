# D-03 源代码、依赖与许可证清单

- 更新日期：2026-09-03
- 状态：边界已冻结；最终 commit、SBOM 和分发审查待补

## 团队原创范围

`backend/engine/`、`backend/foundation/`、`frontend/`、已实现的
`integrations/kylin_agent/`、测试/评测、构建发布和派生项目文档属于 PIXIU 交付
范围。最终清单须按文件/模块给出作者、主要功能和对应提交。

## 上游与系统依赖

| 依赖 | 角色 | 当前已知许可证/边界 |
|------|------|---------------------|
| `third_party/kylin-agent` | 桌面宿主参考/依赖 | 上游许可证文件可确认 GNU Affero GPL v3 族；不宣称原创，不原样作为作品主体；`only` / `or-later` 的精确 SPDX 后缀待人工审查 |
| `third_party/kylin-agent-runtime` | Agent runtime/MemoryProvider | MIT；固定 commit，适配代码另存 Module E |
| `third_party/kylin-coreai-embedding` | 指定 Embedding SDK | GPL-3.0-or-later；按系统分发规则继续审查 |
| `third_party/libkysdk-vector-engine-client` | 指定 Vector Engine 客户端 | Apache-2.0；按系统分发规则继续审查 |

最终源码交付前生成机器可读 SBOM、submodule commit、许可证文本和 NOTICE；检查
密钥、`.env`、个人路径、数据库、日志、缓存和构建产物。若维护上游最小补丁，必须
逐项记录原文件、diff、理由、许可证义务和回合上游策略。

当前 `.deb` 已包含机器可读的 `/usr/share/pixiu/release-manifest.json`，记录四个
submodule 的 gitlink、实际检出 commit/ref、洁净状态和许可证信息；生成器会拒绝
gitlink 与实际检出不一致或含本地修改的子模块。这不替代最终 SBOM、许可证全文及
分发义务的人工复核。`kylin-agent` 当前只确认到许可证族，清单将 SPDX expression
保持为空并标记 `pending-only-or-later-review`，不得将未决后缀固化为授权结论。
清单还明确保留 `agent-runtime` 的上游版本文件 0.9.9 与包元数据 0.9.8 两个不同事实，
最终兼容矩阵须以实际安装 runtime 再验证。
