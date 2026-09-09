# 源码目录迁移与宣传场景交付计划

批准日期：2026-09-10。用户已完整批准本计划对应的只读审查方案，并授权跨模块实施、本地验证与提交。执行优先级：先完成干净的源码目录迁移，再补齐普通用户使用宣传场景时的明显阻碍。优先快速交付，不扩展为内部技术加固、泛化框架或穷举异常工程。不得自行推送、发布、关闭远程 Issue。

## 1. 范围与原则

- 宣传依据仅为 `submission/video-production/storyboard/shots.json`；不改网站、视频工程和第三方 submodule。
- Agent 宿主与 Runtime 继续复用固定的 openKylin 上游，自有补丁归对应源码模块。
- 前端负责桌面与消息呈现；后端负责记忆、Agent 与系统运行；build 只包含构建、打包、CI、交付相关脚本、配置与被忽略的输出。
- Agent 移入 backend 不改变公共 HTTP 接口边界，禁止直接导入记忆引擎和存储私有实现。
- 目录迁移不改变用户数据、scope、API、服务名、安装路径、插件 ID 和应用身份；功能修复另行提交。
- Debian 通用与 V11 原生验证分开。没有真机结果不宣称原生验收通过。
- `docs/DELIVERY_PLAN.md` §0 永久冻结，不改变作品份数、格式、匿名口径，不增加额外必交件。

## 2. 用户缺口与完成标准

| 编号 | 优先级/分镜 | 当前用户阻碍 | 实施与完成标准 |
|---|---|---|---|
| P01 | 首要；s09–s12 | 采集默认 user:local，Agent 默认 user:default，已经采集却问不到 | 贯通授权个人记忆读取，保留历史范围；新用户授权目录后直接问助手能找到内容。不能靠全部共享解决 |
| P02 | 首要；s02/s15 | 普通对话偏好未可靠提取并应用 | 对话设置回答偏好，界面查看与历史回溯，新会话应用，修改后生效 |
| P03 | 首要；s07/s08/s16 | 类别未命中退回全部金额，多份/月份查询不足 | 按类别、月份和多份账单正确汇总；无对应记录明确无结果；修改后重算 |
| P04 | 首要；s18–s23 | 配对成功不等于助手能读到共享内容 | 用户界面明确助手读取范围与新记忆保存范围；授权共享空间可直接询问；私人记忆不隐式共享 |
| P05 | 必要；s16/s22 | 待人工裁决冲突没有结束处理入口 | 查看双方及来源、选择保留记录、确认后结束待处理；查询与同步采用结果 |
| P06 | 必要；s08 | 自动上下文使用的记忆未完整显示来源 | 本轮使用历史记忆可查看对应来源，沿用现有来源界面；普通无记忆回答不强求来源 |
| P07 | 必要；s17 | 流转接口存在，但普通使用缺少明确留存行为 | 正常会话、压缩与切换产生短/中期状态，明确长期保留的触发和确认，正常使用即可完成 |
| P08 | 体验；s24 | 聊天遗忘后需重新开始桌面操作 | 带操作意图前往桌面确认，刷新有效预览，由用户确认删除 |
| P09 | 体验；s11/s12/s26 | 采集边界不清、持续应用使用漏计、简报覆盖不清 | 告知支持格式/目录范围；正确累计持续使用；简报说明范围并可追溯，不扩张复杂主动提醒 |
| P10 | GitHub #2 | 图片账单导入、识别确认、保存、回查不完整 | 按用户最新要求：使用配置的多模态模型理解图片并生成结构化知识草稿；提供图片选择、结果确认、保存及来源查看；OCR 仅为可选辅助能力。该项不是文字账单分镜 s07 的前置条件 |
| P11 | 交付 | 已发布包落后于当前代码修复 | 本地准备同提交的候选包；发布另待用户授权，不将源码完成冒充用户已收到 |

GitHub 现有 Issue：#2「补齐图片账单识别到长期记忆的 V11 安装包闭环」。P01–P11 为本地实施台账，不自动创建远程 Issue。配对、共享同步、手工编辑、桌面遗忘、模型设置、升级已有实现，复用而非重写。

## 3. 目标结构

```text
frontend/
  CMakeLists.txt
  host/{patches,compat}/
  src/
    shell/
    workspaces/{memory,devices,settings,delivery}/
    services/ app/ models/ widgets/
  resources/{icons,message_renderer}/
  tests/ docs/
backend/
  engine/ foundation/
  agent/{pixiu,runtime/patches,tests}/
  agent/kylin_genai_bridge.py
  agent/SOUL.md
  agent/README.md
  platform/{session,updates,migrations,tests}/
  scripts/ docs/
  requirements.txt requirements-build.txt
tests/acceptance/
build/release/
  agent-host/ agent-runtime/ debian/ profiles/ scripts/ tests/ keys/
  构建输入策略、依赖锁、交付配置及被忽略的 out/evidence/dist
third_party/
docs/
.github/workflows/
README.md VERSION AGENTS.md .gitignore .gitattributes .gitmodules
```

`frontend` 的 HTTP/WebSocket 客户端、BackendTypes、UpgradeController、来源客户端、快捷键、通知、托盘均仍属前端。安装升级执行器才属后端。旧 MemoryPanel/PairDialog 等先保留回归，确认无正式调用后单独清理，不在迁移时凭名字删除。

## 4. 完整移动清单

| 原路径 | 新路径 |
|---|---|
| integrations/kylin_agent/pixiu | backend/agent/pixiu |
| integrations/kylin_agent/kylin_genai_bridge.py | backend/agent/kylin_genai_bridge.py |
| integrations/kylin_agent/SOUL.md | backend/agent/SOUL.md |
| integrations/kylin_agent/tests | backend/agent/tests |
| integrations/kylin_agent/README.md | backend/agent/README.md |
| integrations/kylin_agent/message_renderer | frontend/resources/message_renderer |
| build/release/agent-host/patches | frontend/host/patches |
| build/release/agent-host/compat | frontend/host/compat |
| build/release/agent-runtime/patches | backend/agent/runtime/patches |
| build/release/debian/usr/bin/pixiu-user-setup | backend/platform/session/pixiu-user-setup |
| build/release/debian/usr/bin/pixiu-agent-integrate | backend/platform/session/pixiu-agent-integrate |
| build/release/debian/usr/bin/pixiu | backend/platform/session/pixiu |
| build/release/debian/usr/bin/pixiu-backend | backend/platform/session/pixiu-backend |
| build/release/debian/usr/lib/pixiu/launch-agent.py | backend/platform/session/launch-agent.py |
| build/release/debian/usr/lib/pixiu/restart-client | backend/platform/session/restart-client |
| build/release/debian/usr/lib/pixiu/install-update | backend/platform/updates/install-update |
| build/release/scripts/migrate-system-data.py | backend/platform/migrations/migrate-system-data.py |
| frontend/management/HostTray、HostWindowPin、HostCloseGuard、BackendEventStatus | frontend/src/shell 下同名文件 |
| frontend/management/MemoryWorkspace、MemoryWriteDialog、MemoryEditDialog、MemoryAudit、AgentEvidence、AgentEvidenceClient、ForgetPage、MemoryScopes、MemoryScopeControl | frontend/src/workspaces/memory 下同名文件 |
| frontend/management/DevicePage、PairingDialog | frontend/src/workspaces/devices 下同名文件 |
| frontend/management/SettingsWorkspace、PrivacyPage、ServiceStatusPage | frontend/src/workspaces/settings 下同名文件 |
| frontend/management/DeliveryPage | frontend/src/workspaces/delivery 下同名文件 |
| frontend/management/tests | frontend/tests（保留夹具与运行脚本） |

测试与脚本按归属迁移：跨系统生命周期、多设备、消融、性能、安装升级验收归 tests/acceptance；初始化/启动/数据迁移/升级执行器单测归 backend/platform/tests；消息渲染、桌面兼容、主题测试归 frontend/tests；包描述/构建画像/版本/依赖锁/签名/导出/安装钩子测试留 build/release/tests。后端专用评测保留 backend/scripts。

宿主现有 26 个补丁、Runtime 3 个补丁保留顺序与内容。构建过程中的资源导出、元数据清理仍属 build。薄 Runtime 命令包装器、systemd、desktop、polkit、Debian 控制与维护脚本仍可留打包目录。所有许可证随资源移动。

## 5. 必须同步的接线

1. prepare-agent-host.sh：补丁路径、兼容代码、前端文件及渲染资源；通过显式源路径→导出路径映射保留宿主期望布局，避免同时重写上游补丁。
2. frontend CMake：保留 pixiu-management 与回归目标，统一源码入口，不新增第二个产品可执行程序。
3. build-deb.sh：逐项修改源路径，保持 /usr/lib/pixiu 和 /usr/bin 下已安装路径、权限、插件用户激活行为。
4. Python：源码/测试导入、动态导入、子进程、parents[n] 版本定位及插件清单；迁移后不得依赖根 integrations。
5. Runtime wheel：从 backend/agent/runtime/patches 应用补丁，依赖锁和构建工具继续参与同样的构建。
6. CI：普通/V11 工作流、测试发现、路径过滤、资源与验收入口同步更新。
7. agent-supply-chain-policy.json 与记录/审计脚本：新路径输入清单必须齐全，不复用旧提交证据。
8. prepare-submission.py：移除 integrations 白名单，加入 tests；必要技术文档与依赖完整导出，不导出产物。
9. AGENTS、README、全局/模块架构、开发与支持文档同步目录归属；API 功能变化时同步契约；DELIVERY_PLAN §0、赛题归档不改。

## 6. 阶段与验证

| 阶段 | 内容 | 退出条件 | 状态 |
|---|---|---|---|
| M0 | 记录基线与保存计划 | 当前提交、工作区、安装路径、测试入口明确 | 完成：基线 358fe25，工作区干净 |
| M1 | Agent 与渲染资源迁移 | 插件测试、导入和资源检查通过 | 完成：44 项插件测试、渲染资源、版本检查通过 |
| M2 | build 产品实现迁出 | 补丁可应用、启动/初始化/升级/迁移测试通过 | 完成：宿主、Runtime、启动6项、用户服务、激活、迁移及升级助手测试通过 |
| M3 | 正式前端与测试整理 | 管理库与回归编译、界面测试通过 | 完成：正式宿主及管理库编译通过，18 项 Qt 测试通过，真实 Qt 编辑器对 HTTP/SQLite 验证通过 |
| M4 | 验收工具、交付与文档接线 | 无运行时旧路径引用，导出清单完整 | 完成：74 项迁移工具测试，桌面适配与主题通过；源码导出已包含 tests |
| M5 | 干净源码构建 | Git 工作区与无 .git 源码均有可用构建入口 | 宿主完成：4634 文件导出校验、无 Git 宿主编译通过；Runtime 已接线，完整 wheel 构建待 CPython 3.12 环境 |
| F1 | P01/P04 范围贯通 | 私人采集及授权共享可被助手使用 | 已实现：设置界面、授权读取、独立保存位置；124项 API/Provider 测试通过，Qt编译通过 |
| F2 | P02/P03 偏好与账单 | 新会话偏好生效、金额按问题正确计算 | 已实现：对话偏好→版本→新会话上下文；类别/月份/多账单过滤汇总，166 项相关测试通过 |
| F3 | P05–P09 其余宣传链路 | 用户能完成处理，沿用现有界面 | P05–P09 已实现；137 项处理链路测试、129 项来源相关测试通过；来源 Qt 2 项通过，宿主补丁应用通过 |
| F4 | P10 图片账单 | 识别确认保存查询来源；原生验证单列 | 图片选择、确认保存与原图追溯已完成；用户要求图片知识提取改为多模态模型，已替换为现有模型选择与多模态草稿入口，108 项相关测试及 2 项 Qt 测试通过；真实多模态模型与最终包待验证；OCR 不再是发布必需依赖 |
| M6 | P11 完整候选复核 | 新装、升级、会话、来源、同步、采集、遗忘、桌面能力结果记录 | 待开始 |

每阶段本地独立提交。只运行与变更相关的必要测试，失败修复后再推进；不因缺少 V11/模型服务而伪造结果，也不扩展为无期限加固。未执行项目明确记录，不能将目录迁移成功写成功能缺口完成。

迁移期间保持：入口/服务名/应用 ID；公共 API/端口/插件 ID/版本工具契约；数据库/向量/配置/会话/outbox/身份位置；scope、配对、共享和遗忘状态；用户模型与窗口设置。安装旧 integrations 路径是兼容契约，根源码 integrations 则删除。

## 7. 源码交付

包含：完整正式前后端、必要固定上游与许可证、自有补丁、依赖声明与锁、构建画像与脚本、模块/场景测试及脱敏夹具、版本/文件清单/第三方声明、构建运行使用验证规范、必要公开 CI 配置。

排除：pixiu.db 等真实数据、用户配置/密钥/配对凭据/私钥、.git、缓存/venv/构建输出、个人 Agent 配置、内部实名材料、website、submission、录屏制作素材和无必要的历史日志。冻结交付条款不得整节复制到匿名源码说明。

无 Git 源码模式：构建脚本用交付清单核对固定上游快照和版本/构建时间，完成相同补丁与构建；不要求评委取得原仓库或补造 .git。保留文件模式与必要符号链接。最终包与提交版本一致；不自行发布。

## 8. 执行记录

- 2026-09-10：用户批准并要求先迁移再完成宣传体验，禁止延长周期的细节扩展。开始保存计划和实施。

- M5 验证：Runtime 锁测试及 12 项构建输入审计测试通过；当前本机 Python 3.14，不能冒称已生成 CPython 3.12 Runtime wheel 或 V11 最终包。

- 产品修订：用户明确图片知识提取应使用多模态模型，撤销 OCR → 正则草稿作为正式图片账单入口。保留已实现的确认编辑/原图追溯；OCR 仅作为可选辅助接口，不宣称能够独立保证敏感信息检测。
