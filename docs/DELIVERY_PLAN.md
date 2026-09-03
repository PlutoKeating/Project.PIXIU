# PIXIU 最终交付与版本管理计划

> 状态：团队强制交付基线（2026-09-03）
>
> 本文把赛事 D-01～D-10 与团队新增的软件可安装/可升级要求统一为可审查的发布门。
> 官方要求仍以 `OriginProblemDescription.md` 和 `完整赛题要求.pptx` 为准；本文不
> 修改原文，也不把团队新增门槛伪装为官方条款。
>
> 实施顺序、依赖和逐切片完成定义见
> [`IMPLEMENTATION_MASTER_PLAN.md`](IMPLEMENTATION_MASTER_PLAN.md)。

## 1. 单一安装产物

最终向评委提供一个带版本号、架构和校验/签名信息的 PIXIU `.deb`。用户应能在
银河麒麟 V11 图形软件安装器中打开安装，或以一条 `apt install ./pixiu_*.deb`
命令完成；不得要求手工复制源码、创建虚拟环境、逐个安装 Python 包或编辑数据库。

该包必须包含团队原创的记忆服务、记忆控制台和 Module E 适配器，并完成：

- 解包前探测 V11 与架构；由包依赖/严格后端预检验证双 SDK，并在桌面用户激活时
  验证 openKylin Agent 宿主和 0.9.x runtime；
- 安装/升级/卸载脚本幂等，保留用户记忆、配置、设备身份和数据库迁移状态；
- 运行配置由 `postinst` 从只读默认模板首装创建、升级保留并补字段，不作为 dpkg
  conffile；非交互升级不得因每机随机口令产生配置冲突提示；
- 注册服务、桌面入口、图标、日志轮转、权限和故障诊断；
- 依赖可由系统包解析或随包离线提供，安装后可直接启动；
- 上游 Agent 作为已安装宿主依赖，不把未修改的 submodule 冒充 PIXIU 产物；
- amd64/arm64 分别构建与验证，文件名、包元数据和运行架构一致。

### 当前判定

| 能力 | 当前事实 | 发布判定 |
|------|----------|----------|
| 记忆服务 + 控制台 `.deb` | 已有构建、安装、systemd 与桌面入口 | 部分通过 |
| Module E 随包安装 | `.deb` 携带只读 Provider；用户启动时幂等安装并激活，保留端点/scope 等配置、严格画像强制 strict=1；拒绝覆盖非受管同名插件 | **结构通过，最终宿主重验** |
| V11 双 SDK 严格画像 | strict revision 8 同用户产品写入/检索/遗忘/隐藏已通过；兼容组件和用户服务尚未形成最终安装方案，Agent 宿主/runtime 也未安装 | 阻断 |
| 图形安装器双击安装 | 尚无最终版本取证 | 阻断 |
| 离线/全新机安装 | 现有 wheels 路径可用，需最终包重验 | 待重验 |

严格画像采用分阶段门禁：`preinst` 在解包前拒绝错误 OS/架构；双 SDK 是普通
`Depends`，由 apt/dpkg 正常排序安装，再由后端 strict 启动预检拒绝不可用 runtime；
桌面 Agent 与允许位于用户目录的 runtime 由用户态 Provider 激活器验证。严格启动器
不会吞掉激活失败，generic/portable 才保留独立控制台降级。构建器强制
`KYSDK=ON`/`install_strict=1` 成对，组件清单记录最终模式。首次目标运行已证明严格失败
关闭有效，也暴露用户会话 SDK 边界尚未交付化；该边界闭环后才可生成最终证据。
推荐边界已形成待批准的
[`ADR-0002`](decisions/0002-run-native-backend-in-user-session.md)：`.deb` 仍为一次
系统安装，后端改由登录用户的 systemd user manager 运行，数据进入 XDG 用户域，升级
采用用户态停启/健康检查与特权安装两阶段。在 ADR 获批并完成迁移/回滚矩阵前，现有
system service 不删除，H-02/H-03 状态不变。

当前源码新增 `PIXIU_VECTOR_DB_PATH`，strict 启动必须实际装载应用数据库，store 按
进程复用并在退出时断开。当前组合回归 804 项通过；提交 `6f6002e` 的 revision 8
又完成 V11 同用户写入、召回、遗忘和隐藏检查。正式取证器因缺少 Agent 宿主/runtime
而拒绝出证，且该同用户运行方式尚未落实为安装包 user service，因此状态仍为阻断。

官方 AI 子系统是目标系统前置能力，应通过系统提供的 AI 模块管理完成安装/启用。
整套子系统体积大且包含与 PIXIU 无关的模型和引擎，不列为 PIXIU `.deb` 的整体
`Depends`；发布前以同版实测确定 Embedding、Vector Engine 及其 runtime 的最小包集，
并在安装器中对缺失能力给出可操作提示。

Agent 宿主供应链另有独立发布门：官方 0.9.6 二进制可在 V11 启动并连接固定 Runtime，
Gateway 与 PIXIU Provider 无模型探针通过；但公开源码标签不能重建该宿主，0.9.7
发布二进制与目标 V11 ABI 不兼容，Runtime 缓存也不是可复现构建。处理方案与禁止项
见待批准的 [ADR-0003](decisions/0003-package-openkylin-agent-supply-chain.md)。在对应
源码、敏感地址清理、离线锁定和许可证审查完成前，不能把宿主纳入最终单包。
`build/release/scripts/audit-agent-supply-chain.py` 已把该边界变成机器门禁：固定双上游
commit 与 Runtime 三套版本事实，扫描时只披露命中文件名；正式候选以
`--require-ready` 要求 V11 宿主重建、Runtime 离线 wheelhouse、SPDX SBOM 和 NOTICE
同时有效。当前缺证据且上游扫描有命中，报告必须保持 `ready=false`。

## 2. 版本管理唯一真相源

采用 SemVer `MAJOR.MINOR.PATCH`，Debian 包版本为 `MAJOR.MINOR.PATCH-REVISION`。
发布标签、CMake `applicationVersion`、Debian control、Release 资产与更新清单必须
由一个发布版本输入派生；CI 在不一致时失败。

最终版本清单至少包含：

- PIXIU 产品版本、Git commit、构建时间、目标架构与 V11 画像；
- 数据库 schema 版本、API 版本、Module E/provider 版本；
- 兼容的 `kylin-agent`/`agent-runtime` 固定版本范围；
- Embedding/Vector Engine SDK 及运行时版本；
- 每个资产的大小、SHA-256、独立数字签名和发布通道。

图形“关于/更新”页必须展示当前版本、可用版本、通道、组件兼容状态和发行说明。
不得只在多个源码文件手工重复版本号。当前 `0.1.7` 发布预检已同步校验根
`VERSION`、CMake/前端宏及 Module E manifest。构建现生成包内只读
`/usr/share/pixiu/release-manifest.json`，从源码和构建输入记录产品/Debian、Git、
构建时间、架构/profile/KYSDK/Python ABI、API/schema/provider、Agent 上游及双 SDK
源码钉住版本与许可证；CI 会从成包反向提取并核对。上游 runtime 的 `version` 文件
与包元数据当前分别为 0.9.9/0.9.8，清单保留两项事实而不擅自归一。仓库根
`VERSION` 已成为发布脚本和前端 CMake/独立 control 的权威输入，环境变量只能作
一致性断言；Module E 源码只保留 `plugin.yaml.in`，打包/激活时从同一输入生成
`plugin.yaml`。发布工作流与 `publish.sh` 已为每个架构生成无自引用的包外
`.assets.json`，记录 `.deb`/checksum/signature 的大小、SHA-256、commit 和通道，
生成前以固定公钥验证主包签名，并为清单自身生成 checksum + Ed25519 签名；最终
commit/版本/架构从包内组件清单与 dpkg control 交叉核对，且 JSON 记录规范化生成
命令。最终候选仍须归档并复验这六件套；
还须在目标银河麒麟 V11 环境记录 Embedding/Vector SDK 的实际安装包版本、运行时
探测结果及 `/capabilities` 一致性。原生取证器已自动化绑定候选包摘要/commit、已装
manifest、dpkg 版本、Agent runtime 和三个端点，并以独立临时数据库和隔离集合直接
执行 SDK 的装载、集合、向量及断开生命周期；首次真实输出仍待生成，源码 gitlink
不能代替该项实装证据。

三设备证据采用两级门禁：`three-device-evidence.py capture` 必须在各节点本地复用
已经通过的 strict 原生证据并读取 loopback 同步 API，只导出加盐身份/域摘要和版本、
候选包摘要、同步计数；`validate` 汇总恰好三份清单，拒绝跨 run、版本漂移、重复身份、
非完全图、离线/积压或超过 300 秒的采集窗口。它只证明三台 V11 的同版全连接拓扑，
固定 `final_device_evidence=false`；五项跨设备业务场景及最终逻辑视图收敛仍是发布硬门。

## 3. 图形界面一键升级

目标流程：设置 → 检查更新 → 显示版本与发行说明 → 用户点击“一键升级” → 下载 →
校验签名/摘要 → 系统授权 → 原子安装/迁移 → 健康检查 → 受控重启或明确恢复。

发布门：

1. 只选择当前架构与通道的正式资产，拒绝预发布、降级和不兼容组件。
2. HTTPS 之外还要验证独立签名；同一 Release 中的 SHA-256 只证明传输完整性，
   不能单独证明发布者身份。
3. 安装前备份必要配置和 schema 状态；升级失败可恢复上一可用版本，且不丢记忆。
4. `dpkg` 阶段不可强杀；安装后执行包版本、服务/schema/provider 健康检查，全部
   通过才允许 GUI 报告成功。
5. 图形界面完整呈现下载、校验、授权、安装、重启、取消、失败和恢复状态。
6. 更新 PIXIU 自有包，不静默升级上游 Agent 或系统 SDK；兼容性不满足时明确阻断。

当前 `UpgradeController` 已实现版本比较、按架构选择 `.deb`、流式 SHA-256、强制
`.sha256.sig` 资产、重定向白名单、`pkexec` + root-only 二次校验与错误分类；发布
工作流以受保护 Secret 中的 Ed25519 私钥签名，特权 helper 用包内固定公钥在 dpkg 前
验签。helper 还会验证包名/版本/
架构、dpkg 实际安装版本、后端 `/version`、数据库 `/health`/schema 和包内 Provider
版本，健康失败以专用状态返回且不会误报成功。Module E 随包升级会保留用户显式配置，
并在桌面用户上下文重新激活。双架构签名 CI 与 Kylin V11 有效/篡改签名已通过；临时
Ed25519 密钥和两个真实 `.deb` 已完成“旧钥验过渡包、过渡包部署新公钥、新钥验下一包、
旧钥拒绝下一包”的无私钥入库轮换演练。最终仍需补完整 Module E 支持版本矩阵。
自动回滚现已实现 `dpkg-repack` 旧包重建、停服 SQLite 一致性快照、配置备份及失败后
恢复旧包/数据/服务，并区分恢复成功与恢复失败。提交 `ca35117` 的双架构 CI 和
Kylin V11 amd64 跨 revision 健康失败注入均已证明退出码 5、旧版本/配置/数据/服务
恢复；最终候选仍须随完整安装矩阵重验。GUI 成功态的“立即重启”现通过无特权 helper
等待旧客户端退出、再启动新版本；失败可重试或手动打开，安装中不会触发。源码和打包
测试已覆盖，最终 V11 图形升级/重启取证仍待完成。

## 4. 赛事交付文档台账

仓库根目录 [`submission/`](../submission/) 是唯一正式交付生成区；
`submission/submission-plan.json` 把两份官方材料、D-01～D-10、团队单包要求及人工
提供材料映射到最终文件名。当前 `release_ready=false`，全部门通过前打包器拒绝生成
最终 ZIP。`docs/delivery/` 继续作为可审查工作源，不直接充当对外最终文件。

| 编号 | 交付物 | 仓库维护源 | 最终格式 | 当前状态 |
|------|--------|------------|----------|----------|
| D-01 | 项目报告 PPT | `delivery/PRESENTATION_AND_VIDEO.md` | `.pptx` | 内容骨架完成，最终证据待补 |
| D-02 | 技术方案 | `delivery/TECHNICAL_SOLUTION.md` | `.docx` + `.pdf` + Markdown | 工作稿完成，最终数据待补 |
| D-03 | 源代码 | `delivery/SOURCE_AND_LICENSES.md` | 源码包/仓库快照 | 边界完成，SBOM/最终 commit 待补 |
| D-04 | 部署文档 | `delivery/DEPLOYMENT_GUIDE.md` | `.pdf` + Markdown | V11 portable 跨 revision、离线依赖、健康/配置保留已重验；图形、原生最终包待验 |
| D-05 | 演示视频 | `delivery/PRESENTATION_AND_VIDEO.md` | `.mp4` 优先，≤7 分钟 | 脚本完成，录制待完成 |
| D-06 | 用户手册 | `delivery/USER_MANUAL.md` | `.pdf` + Markdown | 工作稿完成，Agent UI 待补 |
| D-07 | 效果/测试报告 | `delivery/TEST_REPORT.md` + `acceptance/` | `.pdf` + 原始 JSON/CSV | portable 已有，最终 V11 待补 |
| D-08 | 记忆流转说明 | `delivery/MEMORY_LIFECYCLE.md` | `.pdf` + Markdown | 设计完成，Agent 实证待补 |
| D-09 | 实际应用案例 | `delivery/APPLICATION_CASES.md` | `.pdf`/报告章节 | 流程完成，最终取证待补 |
| D-10 | V11 适配报告 | `delivery/KYLIN_V11_ADAPTATION_REPORT.md` | `.pdf` + 日志/截图 | V11 portable 升级基线已刷新，最终双 SDK 待补 |

“部分完成”不等于可提交。每份最终文档必须包含版本、日期、作者/审核人、适用提交、
环境、证据链接和已知限制；数据和截图必须能追溯到同一个 release commit。

## 5. 发布与文档门禁

只有以下条件同时满足，才可创建最终候选包：

- H-01～H-03、A-01～A-14、P-01～P-04 和三设备专项按最终 commit 通过；
- 全新 V11 图形安装、命令安装、同版本重装、旧版本升级、失败恢复和卸载通过；
- GUI 一键升级通过签名、授权、迁移、健康检查和恢复测试；
- D-01～D-10 均从“未完成/部分完成”改为“已审核”，且格式符合官方要求；
- 代码、包、PPT、PDF、视频、原始报告的版本和 SHA-256 台账一致；
- 无密钥、个人路径、临时数据、缓存、构建目录或未披露许可证进入交付包。

最终归档应保存只读 manifest，列出每个文件的名称、版本、大小、SHA-256、签名、
生成命令和对应 Git commit。任何文档内容变更都要随代码提交审查，禁止答辩前复制
出脱离仓库维护的“最终版”。

最终外层目录和 ZIP 名固定为
`华南理工大学－OSAgent记忆优化及高效应用研究－PIXIU`；自动打包前还必须放入团队
负责人提供的 PPT、≤7 分钟视频及经报名系统审核通过的盖章报名表。视频/PPT 不由
自动化制作，但与其他文件同样接受存在性、格式、版本和 SHA-256 台账检查。

日常与 CI 使用 `make -C build/release governance` 校验两份官方原件哈希和 Git
工作区洁净度；构建入口继续在生成任何包之前检查应用与 Debian 版本一致性。
