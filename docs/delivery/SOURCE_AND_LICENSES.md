# D-03 源代码、依赖与许可证清单

- 更新日期：2026-09-03
- 状态：边界、Agent SBOM/NOTICE/对应源码和离线依赖审查已通过；最终 commit 冻结待补

## 团队原创范围

`backend/engine/`、`backend/foundation/`、`frontend/`、已实现的
`integrations/kylin_agent/`、测试/评测、构建发布和派生项目文档属于 PIXIU 交付
范围。最终清单须按文件/模块给出作者、主要功能和对应提交。

## 上游与系统依赖

| 依赖 | 角色 | 当前已知许可证/边界 |
|------|------|---------------------|
| `third_party/kylin-agent` | 桌面宿主基座 | 官方 Gitee 元数据声明 `AGPL-3.0`，按 SPDX 规范化为 `AGPL-3.0-only`；固定源码经可审计最小适配后已在 V11 隔离重建，strict 包附对应源码、补丁、构建证据与许可证 |
| `third_party/kylin-agent-runtime` | Agent runtime/MemoryProvider | MIT；固定 commit，适配代码另存 Module E |
| `third_party/kylin-coreai-embedding` | 指定 Embedding SDK | GPL-3.0-or-later；按系统分发规则继续审查 |
| `third_party/libkysdk-vector-engine-client` | 指定 Vector Engine 客户端 | Apache-2.0；按系统分发规则继续审查 |

最终源码交付前生成机器可读 SBOM、submodule commit、许可证文本和 NOTICE；检查
密钥、`.env`、个人路径、数据库、日志、缓存和构建产物。若维护上游最小补丁，必须
逐项记录原文件、diff、理由、许可证义务和回合上游策略。

当前 `.deb` 已包含机器可读的 `/usr/share/pixiu/release-manifest.json`，记录四个
submodule 的 gitlink、实际检出 commit/ref、洁净状态和许可证信息；生成器会拒绝
gitlink 与实际检出不一致或含本地修改的子模块。这不替代最终 SBOM、许可证全文及
分发义务的人工复核。`kylin-agent` 的官方仓库 API 元数据值为 `AGPL-3.0`；SPDX 3.0
将该旧标识拆分并以 `AGPL-3.0-only` 表示仅版本 3，因此清单同时保存官方 URL、原值与
规范化值。仓库 LICENSE 尾部的“or later”文字属于许可证附录中的示例，不能覆盖官方
仓库声明。该结论仍要求最终包附完整对应源码、许可证和 NOTICE。
清单还明确保留 `agent-runtime` 的上游版本文件 0.9.9 与包元数据 0.9.8 两个不同事实，
最终兼容矩阵须以实际安装 runtime 再验证。

供应链探针还确认：固定 Runtime 的 CLI、Python 包和 `version` 文件分别报告 0.9.4、
0.9.8、0.9.9，清单必须原样记录三项事实；Gateway 另实际需要 `aiohttp`，不能只按
名为 `web` 的 extra 推导依赖。上游脚本中的认证式源码地址不得进入交付产物或日志。
赛方/麒麟不能提供可重建宿主时，已批准的 ADR-0003 允许以最小补丁、完整对应源码、
AGPL 义务、锁定 wheelhouse、SBOM 和敏感扫描共同形成可分发组件。

上述条件现由 `build/release/agent-supply-chain-policy.json` 与
`audit-agent-supply-chain.py` 自动检查。普通模式输出可归档 JSON 事实报告；候选发布
必须使用 `--require-ready`，并提供宿主目标架构产物、完整对应源码、构建日志，及
Runtime 全量 wheel、锁文件、离线安装日志；每个实物均须有 SHA-256。SPDX 2.3 必须
精确覆盖固定宿主/Runtime 及 wheelhouse 全部包，NOTICE 必须记录两组件的来源、commit
和许可证边界；任意包列表或非空占位文本不再算有效证据。敏感扫描报告只保存规则与
相对文件名，不保存匹配文本；
当前报告不通过是已知供应链阻塞，不得将“脚本执行成功”误写为“供应链通过”。
审计 JSON 还带 `agent-supply-chain-audit` 类型、release commit 和 pass/fail，最终
A-02 只能收录 `ready=true` 且 `status=pass` 的同版报告。
真实候选的四项文件应由 `record-agent-supply-chain.py` 从宿主产物/源码/构建日志和
wheel `METADATA` 自动记录并生成，避免手填包名、版本或摘要。记录器拒绝不同内容的
同名覆盖及日志/锁文件中的认证式 URL；`--network-isolated` 必须与本次隔离执行日志
同时归档，单独出现仍不构成通过结论。

最终 D-03 不使用会遗漏 submodule 内容的普通 `git archive`。供应链强制门通过后，
由 `build/release/submission_tools/build_source_archive.py` 收集 Git 跟踪文件及四个 submodule 的实际
文件，并把 Agent 供应链证据一并收入归档；内嵌 `SOURCE_MANIFEST.json` 记录 release
commit、submodule commit 和逐文件 SHA-256。`build_submission.py --package` 会复算
这些摘要并检查各源码树，还会把归档中的完整路径集合、文件/符号链接类型和摘要逐项
反向核对到当前洁净 release checkout。任意同名占位压缩包、缺失 submodule，或同时
篡改源码与内嵌 manifest 的归档均会被拒绝。
