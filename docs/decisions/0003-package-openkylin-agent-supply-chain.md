# ADR-0003：固定并交付 openKylin Agent 宿主供应链

- **状态**：建议批准（Proposed）
- **提出日期**：2026-09-04
- **适用范围**：完整 Agent 宿主、Runtime、一键安装、升级、源码与许可证交付
- **前置决策**：[ADR-0001](0001-use-openkylin-agent-host.md)

## 背景

目标银河麒麟 V11 的已配置软件源没有 `kylin-agent` 或 `kylin-agent-runtime` 可执行包。
仓库虽已固定两项官方源码，但源码存在以下可复现缺口：

1. `kylin-agent` 当前 `master` 与 0.9.6 标签均在链接阶段出现多组未定义实现；
   0.9.5/0.9.4 标签还引用不存在的源文件，不能从公开标签重建官方二进制。
2. 官方 0.9.7 amd64 发布包要求目标 V11 不具备的 `CXXABI_1.3.15`；官方 0.9.6
   发布二进制可在 V11 启动，但公开标签不能重现该二进制。
3. 官方宿主包依赖未随发布资产提供的 `kylin-agent-runtime-cache`；其缓存打包器从
   已安装用户目录复制环境，不是由固定源码和锁文件直接生成的可复现构建。
4. 上游 Runtime 安装脚本和 CUA 更新路径包含认证式源码地址并允许运行时联网更新；
   这不满足 PIXIU 的密钥扫描、固定版本、离线安装和升级审计要求。
5. Runtime 同一提交分别报告 CLI 0.9.4、Python 包 0.9.8 和 `version` 文件 0.9.9；
   宿主要求 0.9.9，不能把三项元数据擅自归一。

阶段性探针已经证明架构可行：官方 0.9.6 二进制在 V11 可启动；固定 Runtime commit
可建立用户级 Gateway，`/health` 与 `/api/sessions` 可用；Module E 被发现并选中为
`memory.provider=pixiu`。该探针没有模型配置，也不是最终安装或完整 Agent 验收。

## 建议决策

1. 不从零实现新的 OS Agent，继续遵守 ADR-0001 的宿主/原创边界。
2. 最终安装器必须交付一个固定、可审计的宿主组件和一个由锁定源码构建的 Runtime；
   不允许首次启动再跟随 `master`、在线克隆或静默升级上游组件。
3. 宿主候选优先级为：赛方/麒麟提供的 V11 可重建正式包；其次是取得官方完整对应
   源码后的 0.9.6 包；只有两者均不可得时，才维护最小上游修复集。
4. 如采用最小修复集，补丁独立保存在发布适配区，逐文件记录原因、测试和上游回合；
   不直接改写 `third_party/` gitlink。产物必须清除认证式地址、禁止自主漂移，并按
   AGPL 要求随交付提供完整对应源码、补丁、构建脚本、许可证和 NOTICE。
5. Runtime 从固定 commit 与锁文件构建离线 wheelhouse/隔离环境；明确列出 Gateway
   实际需要但 `web` extra 未声明的 `aiohttp`，不得复制开发者 home/cache 作为产物。
6. 安装与 GUI 升级把 PIXIU、宿主、Runtime、Provider 和双 SDK 作为一个事务检查；
   任一版本、签名、许可证或健康检查失败均不得显示成功。

## 实施门

- S3.1：负责人批准本 ADR，或取得赛方/麒麟提供的 V11 正式宿主包及完整对应源码；
- S3.2：宿主可在干净 V11 从交付源码重建，且敏感地址扫描为零；
- S3.3：Runtime 离线安装只使用固定源码、锁文件和带摘要资产，首次启动不联网更新；
- S3.4：`kylin-agent`、Gateway、Module E 与 PIXIU strict user service 同 UID 启动；
- S3.5：新装、升级、回滚、卸载和源码合规矩阵通过；
- S3.6：再执行多轮、Shell、联网搜索、审批、记忆生命周期与三设备完整验收。

## 暂不允许

- 不把当前不可重建的官方二进制直接嵌入 PIXIU 最终包并声称源码完整；
- 不分发含认证式源码地址的上游脚本或二进制；
- 不把临时用户目录、下载缓存、模型密钥或开发环境状态制成 Runtime 缓存包；
- 不因无模型 Gateway 探针通过而把 A-01～A-10 或 H-01～H-03 标为通过。

## 关联文档

- `../OS_AGENT_INTEGRATION_ASSESSMENT.md`
- `../DELIVERY_PLAN.md`
- `../IMPLEMENTATION_MASTER_PLAN.md`
- `../delivery/SOURCE_AND_LICENSES.md`
- `../../build/release/README.md`
