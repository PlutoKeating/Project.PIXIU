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
| `third_party/kylin-agent` | 桌面宿主参考/依赖 | AGPL-3.0；不宣称原创，不原样作为作品主体 |
| `third_party/kylin-agent-runtime` | Agent runtime/MemoryProvider | MIT；固定 commit，适配代码另存 Module E |
| `third_party/kylin-coreai-embedding` | 指定 Embedding SDK | 按上游许可证与系统分发规则审查 |
| `third_party/libkysdk-vector-engine-client` | 指定 Vector Engine 客户端 | 按上游许可证与系统分发规则审查 |

最终源码交付前生成机器可读 SBOM、submodule commit、许可证文本和 NOTICE；检查
密钥、`.env`、个人路径、数据库、日志、缓存和构建产物。若维护上游最小补丁，必须
逐项记录原文件、diff、理由、许可证义务和回合上游策略。
