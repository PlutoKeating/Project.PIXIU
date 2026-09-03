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

- 安装前探测 V11、架构、openKylin Agent 宿主、Embedding 与 Vector Engine；
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
| Module E 随包安装 | `.deb` 携带只读 Provider；用户启动时幂等安装、保留配置并激活；拒绝覆盖非受管同名插件 | **结构通过，最终宿主重验** |
| V11 双 SDK 严格画像 | 独立 strict profile/workflow 已实现；首次全链路证据未生成，H-02 未通过 | 阻断 |
| 图形安装器双击安装 | 尚无最终版本取证 | 阻断 |
| 离线/全新机安装 | 现有 wheels 路径可用，需最终包重验 | 待重验 |

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
不得只在多个源码文件手工重复版本号。当前 `0.1.7` 发布预检已同步校验 CMake、
前端宏、Debian 默认版本及 Module E manifest；后续仍须收敛后端/API/schema/宿主
manifest，并改为由单一发布输入生成，而不是长期依赖多处手工编辑。

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
并在桌面用户上下文重新激活。双架构签名 CI 与 Kylin V11 有效/篡改签名已通过；最终
仍需补：密钥轮换实证、完整 Module E 支持版本矩阵、
自动回滚现已实现 `dpkg-repack` 旧包重建、停服 SQLite 一致性快照、配置备份及失败后
恢复旧包/数据/服务，并区分恢复成功与恢复失败；真实故障注入证据待补。另需受控前端
重启，以及最终 V11 图形升级取证。

## 4. 赛事交付文档台账

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

日常与 CI 使用 `make -C build/release governance` 校验两份官方原件哈希和 Git
工作区洁净度；构建入口继续在生成任何包之前检查应用与 Debian 版本一致性。
