# ADR-0002：原生后端运行于桌面用户会话

- **状态**：建议批准（Proposed）
- **提出日期**：2026-09-04
- **适用范围**：银河麒麟 V11 strict 画像、安装/升级、数据与 SDK 生命周期
- **前置决策**：[ADR-0001](0001-use-openkylin-agent-host.md)

## 背景

目标 V11 实测确认，指定 Embedding runtime 与 Vector Engine 均按调用进程的有效 UID
提供 Unix socket；上游 openKylin Agent 也运行在登录桌面用户会话。当前
`pixiu-backend.service` 却以系统账户 `pixiu` 运行，因此无法访问桌面用户的 AI
runtime。strict 模式正确地失败关闭，但 H-02/H-03 无法形成产品生产链证据。

Embedding 还存在独立系统组件契约问题：runtime 生命周期层要求模型元数据提供
对象型 `model_catalog` 及 `TEXT`/`IMAGE` 目录；目标系统枚举返回 err=3，显式模型
初始化仍返回 err=10。改变服务账户不会掩盖或自动修复该问题，两个阻断必须分别闭环。

PIXIU 处理的是用户记忆、行为采集、Agent 会话与设备身份。让系统级共享守护进程
代替多个桌面用户访问这些数据，会同时引入跨用户隔离、AI socket 代理和端口归属问题。

## 决策

银河麒麟 V11 strict 产品画像采用“系统安装、用户运行”的边界：

1. `.deb` 继续由系统包管理器一次安装，程序、原生扩展、Provider、签名公钥和
   systemd unit 均为 root 所有、普通用户只读。
2. 后端改为 systemd **user service**，由 PIXIU 桌面启动器或 Agent Provider 在登录
   用户上下文幂等启动；不由 `postinst` 冒充用户会话启动。
3. strict 后端、openKylin Agent、Embedding runtime 和 Vector Engine 必须具有相同
   有效 UID。能力端点和原生取证记录 UID 一致性，但不得记录个人用户名、主机信息或
   本地调试拓扑。
4. 新安装的数据、配置、同步身份和日志进入 XDG 用户域：
   `$XDG_DATA_HOME/pixiu`、`$XDG_CONFIG_HOME/pixiu`、`$XDG_STATE_HOME/pixiu`；配置与
   私钥材料权限为当前用户独占。程序不得跨用户扫描或复用记忆库。
5. 当前产品支持一个活动图形会话使用 loopback API。服务启动必须对端口占用给出明确
   诊断，不得连接到另一 UID 的 PIXIU 实例。多并发登录会话改用 Unix socket/端点发现
   属于后续扩展，不是本赛题验收前提。
6. 旧系统服务和 `/var/lib/pixiu` 数据必须通过版本化、可回滚的一次性迁移切换；迁移
   前验证源数据库完整性，复制后校验 schema/身份/计数，成功前保留源数据。禁止由
   新用户服务直接长期读取 root/系统账户数据。
7. 图形升级改为两阶段：用户态客户端先有序停止 user service；特权 helper 只验证
   签名并安装 root-owned 包；返回用户态后重启服务并执行 `/version`、`/health`、
   `/capabilities`。健康失败必须触发现有签名回滚协议，不能提前显示成功。
8. Debian `KYSDK=OFF` 仍采用同一用户服务结构并显式报告 portable；不得借两种服务
   拓扑产生只有开发环境能通过的行为。

## 被否决的方案

### 继续使用系统账户并启动另一套 AI runtime

否决。它与桌面 Agent 不同 UID，可能重复加载大模型，并把用户级系统能力错误变成
机器级共享能力；仍需解决用户数据归属。

### 在系统后端与用户 SDK 之间新增代理

暂不采用。代理需要认证、UID 路由、流量限额、崩溃恢复及双 SDK 完整 RPC 映射，
新增高权限攻击面；对单用户桌面作品没有足够收益。

### 放宽 socket 权限或转发现有 socket

否决。改写系统 runtime 权限越过官方隔离边界，升级后不可控，也不能作为合规交付。

## 实施门与验收

- R2.1：user unit、启动器、Provider 激活和 strict 能力预检均以同一 UID 运行；
- R2.2：新装、旧版迁移、重装、升级失败回滚、卸载保留数据分别通过；
- R2.3：端口伪服务/其他 UID 实例不能通过组件身份与版本握手；
- R2.4：同一 strict 候选完成真实 Embedding、Vector 建库/写查删及产品 API 生命周期；
- R2.5：图形升级从用户态停服到健康/回滚完成，全程不丢记忆和同步身份；
- R2.6：Debian portable 与 V11 strict 结果分栏，官方两份原件哈希保持不变。

本 ADR 获批准前，可以补测试、迁移设计和打包清单，但不得删除旧 system service 或
移动用户数据。批准后按“测试 → user unit/启动 → 数据迁移 → 升级协议 → V11 取证”
分成独立提交实施。

## 关联文档

- `../IMPLEMENTATION_MASTER_PLAN.md`
- `../DELIVERY_PLAN.md`
- `../AcceptanceTestSpecification.md`
- `../OS_AGENT_INTEGRATION_ASSESSMENT.md`
- `../../build/release/README.md`
