# PIXIU 赛事正式交付区

本目录用于生成和存放华南理工大学 PIXIU 团队的最终赛事交付文件。它不是日常构建
输出目录，也不得放入未脱敏日志、开发机信息、密钥、临时数据库或未经审核的证据。

## 权威口径

交付清单同时执行两份只读官方材料：

- `docs/OriginProblemDescription.md` 第五、八节；
- `docs/完整赛题要求.pptx` 第 21 页。

官方核心作品为项目报告 PPT、技术方案及测试结果 Word/PDF、源代码及规范；PPT 细则
另要求部署文档及不超过 7 分钟的 `.avi`、`.mp4` 或 `.wmv` 功能演示视频。平台文字
方案要求技术文档/用户手册覆盖需求、架构、算法、实现、部署、操作、数据集、对比
实验和量化指标，并提供记忆流转说明、至少一个实际案例及 V11 适配测试报告。经报名
系统审核通过的盖章报名表须同步报送，但它不是由代码仓库自动生成的作品文件。

最终外层名称严格采用：

`华南理工大学－OSAgent记忆优化及高效应用研究－PIXIU`

## 目录约定

- `submission-plan.json`：唯一的机器可读交付清单、来源和就绪门；
- `build_submission.py`：校验官方原件、release commit、Git 洁净度和全部文件，生成
  `SHA256SUMS` 与最终 ZIP；
- `build_source_archive.py`：在官方原件、Git/submodule 和 Agent 供应链门全部通过后，
  生成包含四个 submodule 实体内容、供应链证据及逐文件摘要清单的 D-03 源码包；
- `render_documents.py`：把 D-02/D-03/D-04/D-06～D-10 的 Markdown 权威源排版为
  A4 DOCX/PDF；草稿带醒目禁提交标识，最终模式在其他 release gate 通过前拒绝运行；
- `build_evidence_archive.py` + `evidence-policy.json`：要求并交叉校验双 SDK、完整
  Agent、性能、三设备、安装升级、数据集与供应链七类同版原始证据；
- `final/`：最终文件生成位置，构建产物不进入 Git，避免源码包递归包含自身；
- `review/`：本机可重复生成的审阅实物，受 Git 忽略；不得复制到 `final/` 冒充已验收文件；
- `build/release/evidence/`：候选供应链实物的受忽略工作目录；内容不入 Git，但由
  D-03 归档器复制进源码交付包并纳入逐文件摘要；
- `human-input/`：说明必须由团队负责人提供的 PPT、视频和盖章报名表。

当前 `release_ready=false` 是有意的。只有 H-01～H-03、Agent 可重建离线供应链与
生命周期闭环、最终 V11 指标、
三设备同步、安装/升级和 D-01～D-10 全部以同一 commit 通过并审核后，才可填写最终
commit、把各门设置为 `passed`。

截至当前，仓库能够自行维护和生成 D-02、D-03、D-04、D-06、D-07、D-08、D-09、
D-10 及 R-01 相关安装资产；在全部正式门关闭前只能生成带水印审阅稿。团队负责人
最终需要提供的外部材料严格收敛为 D-01 项目报告 PPT、D-05 ≤7 分钟演示视频、盖章
报名表，并对自动生成文档签字审核。确定性 Mock 只服务工程调试，不能作为缺失的
`agent_lifecycle` 正式主记录放入原始证据 ZIP。

当前审阅目录应包含下列已准备内容：

| 子目录 | 内容 | 状态 |
|--------|------|------|
| `00-软件候选/` | `pixiu_0.1.7-1_amd64.deb`、同名 `.sha256`、`native-sdk-smoke.json`、`agent-supply-chain-report.json`、`mock-agent-full.json`、`mock-agent-shared-memory.json`、`ui-agent-workspace.png` | 可审阅；正式签名和最终同版矩阵待补 |
| `02-技术方案/` | DOCX + PDF | 带草稿标识 |
| `03-源代码及规范/` | 含四个 submodule 实体的源码审阅包 + 许可证 PDF | 可审阅；冻结后改为正式文件名 |
| `04-部署文档/` | 部署指南 PDF | 带草稿标识 |
| `06-用户手册/` | 用户手册 PDF | 带草稿标识 |
| `07-效果与测试/` | 测试报告 PDF | 带草稿标识；七类正式原始证据未齐 |
| `08-记忆流转/` | 记忆流转说明 PDF | 带草稿标识 |
| `09-应用案例/` | 应用案例 PDF | 带草稿标识 |
| `10-V11适配/` | V11 适配报告 PDF | 带草稿标识 |

最终门全部通过后运行：

```bash
python3 submission/render_documents.py --check
python3 submission/render_documents.py --draft-output DRAFT_DIRECTORY
python3 submission/render_documents.py --render-final
python3 submission/build_evidence_archive.py --build \
  --package FINAL_DEB --output RAW_EVIDENCE_ZIP \
  --record agent_supply_chain=AGENT_SUPPLY_CHAIN_JSON \
  --record native_sdk=NATIVE_SDK_JSON \
  --record agent_lifecycle=AGENT_LIFECYCLE_JSON \
  --record performance=PERFORMANCE_JSON \
  --record three_device=THREE_DEVICE_FINAL_JSON \
  --record install_update=INSTALL_UPDATE_JSON \
  --record dataset=DATASET_MANIFEST_JSON \
  --attachment OPTIONAL_CSV_OR_SANITIZED_LOG
python3 submission/build_source_archive.py \
  --root . --evidence-dir AGENT_EVIDENCE \
  --output "submission/final/华南理工大学－OSAgent记忆优化及高效应用研究－PIXIU/03-源代码及规范/Project.PIXIU-source.tar.gz"
python3 submission/build_submission.py --check
python3 submission/build_submission.py --package
```

`--draft-output` 只能指向 `submission/final/` 之外的审阅目录，所有页面自动标注
“草稿预览，不得提交”。`--render-final` 要求 Git 位于 `release_commit` 且洁净，除
`documents-reviewed` 外所有门已通过，并拒绝状态行仍含“待补/未完成/工作稿”的源文档；
生成后由负责人审核，再把 `documents-reviewed` 和总 `release_ready` 置为通过。
渲染工作站需要 LibreOffice Writer 与 `pdfinfo`，它们只是出文档工具，不进入运行包。
原始证据归档的 7 个 `--record` 缺一不可；附件可重复提供。所有主记录必须为
`status=pass`，按策略给出真实设备属性和关键检查，并与当前 commit、最终 `.deb`
SHA-256 一致；供应链报告另须 `ready=true`。生成和复验都会拒绝认证 URL、私钥、
常见令牌与个人目录路径，ZIP 内 `EVIDENCE_MANIFEST.json` 保存全部成员摘要。

`agent_lifecycle` 主记录必须来自 `agent-lifecycle-evidence.py` 的重启前/后两阶段实测；
中间 capture state 含原始会话标识和随机标记，只用于续跑，禁止作为附件进入归档。
最终 `agent-lifecycle.json` 不含对话和工具载荷，并可由该工具的 `validate` 子命令复核。

`performance` 主记录必须由 `final-performance-evidence.py` 生成并通过离线复核；其五个
输入（原生、Agent、数据集、逐样本报告、三变体消融矩阵）应作为去敏附件一并保留，
否则即使汇总百分比达标，也不满足 D-07 原始结果要求。
消融附件还必须包含固定任务集、三份逐任务报告、六份去敏 Runtime 快照和分布式节点
manifest；归档器会复算全部结果并核对跨节点身份。不得归档可能含密钥的原始
`config.yaml` 或 `.env`。
其中逐样本报告必须来自安装包内 `capture_final_eval.py`，携带真实双 SDK runtime、安装
路径、native 证据摘要和同版 release identity；归档器会再次核对，portable 报告无效。

`install_update` 主记录必须由 `install-update-evidence.py finalize` 汇总。六种操作的
operation JSON、动作前后快照和 proof 均须作为 `--attachment` 加入；归档器会按摘要
找到并打开它们，重验状态转换、健康和数据保留。GUI 操作只能由真实前端升级控制器
产生，不能用直接安装命令冒充。

`dataset` 主记录及其冻结 JSON 必须由 `final-dataset-manifest.py` 在 clean release commit
生成；二者都应归档，且性能报告的 dataset 摘要必须与 manifest 一致。manifest 会明确
其为附录 A 派生的团队合成 test-only corpus，不得在交付文案中改称官方数据集。

归档器会深度复核全部七类主记录，并要求 Agent 引用归档内 native、
性能引用三类主记录及实际逐样本/消融附件、dataset manifest 引用实际冻结 JSON。
它会重新规范化数据集、重新评分两个性能附件，逐层复核安装 operation/快照/proof，
递归重建消融任务/变体/快照与三设备拓扑/场景，并复核 Agent 供应链全部构建、离线安装与许可证实物；
外层字段正确但内容或摘要不符仍会失败。

`--package` 在任何门未通过、文件缺失、命名/格式错误、官方原件哈希改变或工作区不
洁净时都会失败。D-07 的 `three-device-final-suite.json` 还必须满足最终三设备契约，
并与 `release_commit` 和最终 `.deb` SHA-256 一致；仅将任意 JSON 放入目录无法通过。
D-03 也不接受普通 `git archive` 或任意同名压缩包：最终打包器会读取内嵌
`SOURCE_MANIFEST.json`，逐项复算源码和 Agent 供应链证据摘要，并要求后端、前端、
Module E、发布工具、交付文档及四个固定 submodule 的实体文件全部存在；完整路径集合、
成员类型和摘要还必须与当前洁净 release checkout 相同，不能同时替换源码和 manifest。
最终打包器还会检查 PDF/DOCX/PPTX/ZIP/视频的实际文件签名或内部结构，复算 `.deb`
摘要并用仓库固定 Ed25519 公钥验证签名，不能用改扩展名的占位文件过门。
其中 `原始证据.zip` 还会再次运行七类证据策略校验，普通可读 ZIP 不算通过。
视频和 PPT 不由该渲染器生成；其他文档及源码包必须在最终
候选完成后由仓库维护源生成并经人工审核，禁止以当前工作稿占位提交。
