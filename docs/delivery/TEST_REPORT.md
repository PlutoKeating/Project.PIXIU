# D-07 效果与测试报告工作稿

- 更新日期：2026-09-03
- 状态：portable 开发基线已有；最终 V11 双 SDK/Agent/三设备报告未完成

## 测试口径

最终报告按 H-01～H-03、A-01～A-14、F1～F7、P-01～P-04、N-01～N-08 和
R-01～R-06 分层。每组结果记录 release commit、机器、V11 版本、架构、SDK/runtime、
数据集版本、冷热口径、样本数、原始输出和失败样本。

## 已有开发基线

portable 自建数据集记录为偏好 100%、知识召回 100%、冲突 96%、P95 115ms；它只
证明通用路径可回归，不能证明 H-01～H-03。2026-09-03 最近全量快照为 Engine
145 项、Foundation 619 项、Module E 16 项（合计 pytest 780 passed），前端 ctest
37/37；Python 回归另报告 11 条依赖弃用/异步线程退出告警但无失败。新增安装健康
切片另由 7 项单元测试及发布 helper 脚本覆盖。提交最终稿前仍必须从
同一候选 commit 重新运行并保存原始日志。

同日 V11 amd64 portable 包完成非交互跨 revision 升级，配置文件摘要保持一致、
后端恢复 active、能力端点识别 V11 且如实返回双后端 `portable` 和
`contest_ready=false`。该结果只覆盖 D-04/R-05 的一个升级切片。

当前升级 helper 已自动校验包名/版本/架构、实际 dpkg 版本，以及后端产品/API/
schema、数据库就绪状态和包内 Provider 版本；健康失败不会被 GUI 误报为成功。该
签名 CI run `33769179956` 在提交 `1bd948b` 上生成 amd64/arm64 三件套，两架构
SHA-256 与 Ed25519 固定公钥复验均通过。amd64 资产在 Kylin V11 经特权 helper
完成有效签名安装与健康检查；篡改签名在 dpkg 前以退出码 3 拒绝，已装版本、配置与
核心数据摘要不变。提交 `ca35117` 的 CI run `33770727108` 在 amd64/arm64 均完成
健康失败注入和自动恢复；Kylin V11 amd64 进一步从已装 `0.1.7-4` 尝试安装签名
`0.1.7-1`，注入健康失败后 helper 以退出码 5 恢复 `0.1.7-4`。恢复前后配置摘要、
evidence/knowledge/preference/同步身份/peer 逻辑计数和数据库完整性一致，服务 active，
事务临时目录无残留。受控重启新增控制器成功态/调度失败测试、对话框“立即重启”
测试、helper 参数/等待路径测试和并行临时文件资源锁；前端 37 个 CTest 目标在并行
运行下全绿。发布测试另以临时 Ed25519 密钥构建两个真实 `.deb`：旧信任锚验过渡包，
从已验包部署新公钥，新信任锚验下一包，并确认旧锚拒绝该包；私钥和临时包均不入库。
发布组件清单测试已覆盖确定时间、构建输入、版本漂移拒绝、API/schema/provider 解析、
四个 submodule commit 与上游 runtime 双版本事实；本地 generic 包已从 `.deb` 反向
提取并解析该清单。CI 另要求洁净源码、commit、Debian 版本、架构和画像完全一致。
开发证据仍不包含最终 V11 图形升级后重启操作。

提交 `30e0d64` 的 Kylin V11 amd64 目标回归进一步验证：兼容画像本地构建和前端
ctest 37/37 通过，cp312 wheels 完整随包且安装时采用离线路径；测试包
`pixiu_0.1.7-4_amd64.deb` 的 SHA-256 为
`f849efacfa83154b287fa081844051aaf78893fe5ececb2099002e1abb210f59`。
从 `0.1.7-3` 跨 revision 升级后服务 active，配置摘要和 evidence/knowledge/
preference/同步身份与 peer 的逻辑计数摘要不变；再经特权 helper 同版重装，安装健康
返回 `0.1.7`、schema 12、数据库 ready。`/capabilities` 同时返回 Kylin V11、两个
runtime 均为 portable、`contest_ready=false`，因此只计 D-04/R-05 兼容切片。

## 最终必须补齐

- V11 中 Embedding 与 Vector Engine 实际建库/写入/查询/删除及严格失败证据；
- 多会话/多轮、自主规划、Shell/联网搜索、审批、记忆召回/写入和新会话复用；
- 三设备并发、离线、重连、冲突、墓碑和收敛；
- 全新图形安装、同版重装、跨版升级、坏签名、断网、取消，以及最终候选上的失败回滚和数据保留重验；
- 四项性能的置信口径、失败分析、限制、对照实验和优化方向。

最终表格和图只从 `docs/acceptance/` 的同版 JSON/CSV 生成，不手工修改统计结果。
