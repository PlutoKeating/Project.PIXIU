# 同步网络图形化管理 Design Spec

> 2026-09-06 代码复核：发现/请求/确认、同步开关和退出网络 UI 已实现；退出复用逐节点 revoke，无 /sync/leave 或 /sync/now 端点。三逻辑节点协议回归不等于三台物理 V11 场景全部通过。
> 下文实施步骤、旧接口草图和测试数字保留作阶段历史，不作为当前操作手册；当前契约见 docs/API.md，发布见 docs/DELIVERY_PLAN.md。

> 日期：2026-08-26 · 状态：待规划
> 定位：将 PIXIU 已实现的去中心化网状同步（Gossip/反熵/CRDT/LWW）从后台能力升级为**用户可感知、可掌控的日常功能**，作为面向家庭/团队多人场景的核心亮点。

## [S1] 背景与目标

PIXIU 的多人场景价值主张是"多设备集体 agent memory 同步"：设备两两配对形成全连接网状结构，所有设备的记忆趋于一个共同维护、一致认可的最新版本。当前该能力：
- 后端已实现（sync/ 2054 行：Ed25519、QR/PIN 配对、mDNS、TLS mTLS、Gossip、反熵、CRDT、物化器），但**默认关闭**（`PIXIU_SYNC_NETWORK_ENABLED=false`），纯 env 配置，无运行时开关；
- mDNS 仅服务**已配对设备**（`TrustedPeerDirectory` 信任过滤），未配对设备不可被发现；
- 配对为**令牌式**（QR/PIN），无"一键发现 + 对方确认"的 GUI 主路径；
- 冲突处理为 **LWW 人人平等**（后写者胜），无"main 主干 + 快进检测 + 人工仲裁"语义；
- 前端同步 Tab 当时仅有「配对设备」「刷新」入口 + 节点列表/摘要，无总开关/发现/退出/冲突入口。

本批次目标：**默认开启、GUI 可管理、main 主干 + 快进 + 人工仲裁**。

## [S2] 后端改造

### [S2.1] 发现扩展：未配对设备广播与发现
- `MdnsDiscovery` 扩展：除注册已配对设备通告外，广播**未配对状态**（`pairable=1` 属性），使局域网内其他 PIXIU 实例可在发现列表中看到本机；
- 新增 API `GET /sync/discover` → `{"devices": [{"device_id","device_name","address","pairable","paired"}]}`（mDNS 浏览结果 + 与本地 peers 合并标注）；
- mDNS 生命周期：随 sync runtime 启动（默认开启后生效）。

### [S2.2] 确认式配对通道
- 保留 QR/PIN 令牌流程（`PairingManager.create_token/pair`）为备选；
- 新增主路径：
  - `POST /sync/pair/request` `{target_device_id}` → 目标机生成一次性确认请求（含 6 位 PIN + 双方设备名 + 过期时间）；
  - 目标机 UI 弹窗「XX 请求与你配对 [PIN] 确认/拒绝」→ `POST /sync/pair/confirm` `{request_id, accept}`；
  - 接受后复用现有 `pair` 签名交换完成入网；
  - 请求存储复用 sync store 新增 `pair_requests` 表或内存表（TTL 60s），拒绝/超时清理；
  - 事件：经 WS 广播 `pair_request` 帧（`event="pair_request"`）给目标机前端。
- 契约更新写回 `docs/API.md`。

### [S2.3] main 主干 + 快进检测 + 分叉转人工
- 语义定义：
  - **main** = 全网版本向量的**共识收敛点**（所有在线 peer 已 ACK 的最新 op 集合的 LWW 合并结果）；
  - **快进（fast-forward）**：本地 main 是远程 main 的因果祖先（`compare_clocks(local, remote) == Before` 或本地未见过远程 op）→ 直接应用远程 op 集合并推进本地 main；
  - **分叉（fork）**：本地与远程 main 存在**并发 op**（`compare_clocks == Concurrent`）且内容语义矛盾 → 触发人工仲裁。
- 实现位置：`backend/foundation/sync/` 新增 `mainline.py`（或扩展 `oplog.py`/`crdt.py`）：
  - `class Mainline`：维护本地 main 版本向量 + 已合并 op 集；`try_fast_forward(remote_ops) -> FastForwardResult(Ok|Forked)`；
  - Fork 时：调 `backend/engine/conflict` 的 `Arbiter.detect`（NEW_WINS/MERGE 自动吸收，MANUAL 生成 `ConflictRecord`）；MANUAL 记录经 WS `conflict_detected` 广播（既有事件路径）。
- 行为边界：纯自动路径（快进成功 / NEW_WINS / MERGE）不打扰用户；仅 MANUAL 分叉进 UI。**不改变** Gossip/反熵传输机制与存储 schema 主体；`materializer` 应用层补 mainline 判定。
- 既有 `LWWElementSet` 保留为 op 级合并原语，mainline 在其上层做语义判定。

### [S2.4] 默认开启 + 运行时开关
- `pixiu.env` 与 `.env.example`：`PIXIU_SYNC_NETWORK_ENABLED=true`（默认开）；
- 新增运行时开关接口（替代纯 env）：
  - `GET /sync/status` 响应扩展 `{"enabled": true, "paused": false, ...}`（`paused` = 传输暂停）；
  - `PUT /sync/settings` `{"enabled": bool, "paused": bool}` → 持久化 + 热生效（enabled=false 停止 mDNS 注册与监听并断开；paused=true 停止推送但保留配对与发现）。
  - 配置持久化：复用 `monitor_config` 同模式的 sync_settings KV（或 env 为初始默认、运行时覆盖写 KV——实现时二选一并注明，倾向 KV 覆盖 env）。
- 安全提示：enabled=true 时 mDNS 广播本机存在（设备名+IP 暴露于局域网）；UI 引导文案说明。

## [S3] 前端改造

### [S3.1] 同步 Tab 升级（`frontend/src/widgets/MemoryPanel.cpp` 同步 Tab + `SyncController`/`HttpBackendTransport` 扩展）
控件结构（自上而下）：
1. **总开关**（objectName=`syncMasterSwitch`，QCheckBox，默认开；初始值 = GET /sync/status.enabled；切换 → PUT /sync/settings；off 时下方控件禁用并提示「同步已关闭」）；
2. **暂停传输开关**（objectName=`syncPauseSwitch`，QCheckBox；切换 → PUT /sync/settings.paused；off 态仅暂停数据流，节点列表仍显示）；
3. **状态摘要**（既有 `syncStatusLabel`/`syncSummaryLabel` 复用，追加 `enabled/paused` 状态文案）；
4. **附近设备发现列表**（objectName=`discoveredDeviceList`，QListWidget；每项：设备名+地址+「配对」按钮；数据源 GET /sync/discover；点击配对 → POST /sync/pair/request → 等待对方确认态；收到 WS `pair_request` → 弹确认框）；
5. **已配对节点列表**（既有 `peerList`；**移除每个节点的 RevokeDialog 解绑入口**——功能移除，节点仅展示名称/在线/上次同步）；
6. **「退出网络」按钮**（objectName=`leaveNetworkButton`，确认对话框「将解除全部 N 台设备配对并停止同步，确定？」→ 逐台 revoke 或新增 `POST /sync/leave`（实现选一，倾向逐台复用既有 revoke 端点）→ 回单机态）；
7. **「待处理冲突 N」横幅**（objectName=`syncConflictBanner`，仅 N>0 可见；点击 → `showConflictTab()` 聚焦冲突 Tab）。
- i18n：全部新文案 tr() 中文源文本；Task 收尾 lupdate/lrelease。
- 新增交互态：pairRequestPending / pairConfirmDialog / leavingNetwork（防重复点击）。

### [S3.2] 冲突 Tab 增强（`MemoryPanel` 冲突 Tab + ConflictController）
- 现有冲突列表已展示 MANUAL `ConflictRecord`；同步分叉产生的记录经既有 `conflict_detected` WS 事件进入同一列表（后端 S2.3 保证格式一致），前端**仅需**：横幅计数联动 + 冲突条目来源标注「同步冲突」（`source` 字段新增 `"sync"`，既有 `"write"` 兼容展示）。
- 无新裁决 UI：沿用现有"保留本地/采用远程/手动合并"操作（操作经既有端点，契约扩展字段）。

## [S4] 契约与文档
- `docs/API.md`：新增 GET /sync/discover、POST /sync/pair/request、POST /sync/pair/confirm、PUT /sync/settings（可选 POST /sync/leave、POST /sync/now）；扩展 GET /sync/status 字段；WS 事件 `pair_request`；ConflictRecord.source 枚举扩展。
- `frontend/docs/MONITOR_API_REQUIREMENTS.md` 不动（属监控批次）；同步契约独立章节加至 docs/API.md。
- README 核心亮点第一条「去中心化记忆网络」更新实现状态描述（默认开启 + GUI 管理 + main 主干人工仲裁）。

## [S5] 测试策略
- 后端 pytest：
  - discovery：未配对设备可被发现、paired 标注正确、mDNS 生命周期 start/stop；
  - pair request/confirm：请求创建/TTL 过期/拒绝/接受后入网、PIN 校验、重复请求幂等；
  - mainline：快进成功（祖先）、分叉检测（并发矛盾）、NEW_WINS/MERGE 自动吸收、MANUAL 生成 ConflictRecord、offline 恢复；
  - settings：默认开、PUT 持久化、热生效（enabled/paused 语义）；
- 前端 ctest（offscreen）：
  - syncMasterSwitch 默认开且 PUT 生效、off 禁用下级控件；
  - syncPauseSwitch 语义；
  - discoveredDeviceList 渲染 + 配对按钮触发 request；
  - pairConfirmDialog 确认/拒绝路径；
  - leaveNetworkButton 确认框 + 逐台 revoke 调用；
  - syncConflictBanner 计数显示与跳转；
  - 既有 t_app_navigation 同步相关用例适配（RevokeDialog 移除影响）。
- 全量回归：后端全量 pytest + `frontend/scripts/regression.sh`（OFF/ON 双路径）。

## [S6] 范围边界（不做）
- 不做跨公网同步（仅局域网 mDNS）；
- 不做自动冲突裁决升级（维持 NEW_WINS/MERGE/MANUAL 三分法，不引入 AI 裁决）；
- 不改 Gossip/反熵/存储传输机制主体；
- 不新增单设备解绑替代（按用户决策：移除单设备解绑，仅整网退出）；
- 不做同步历史可视化/审计页。

## [S7] 风险与开放点
- 默认开启的安全暴露面（mDNS 广播）——已在 S2.4 提示，UI 引导关闭入口；
- main 主干语义与既有 LWW 合并的兼容性：新 mainline 判定置于 CRDT 之上，需对既有三节点收敛测试回归不破坏；
- pair_request WS 帧在目标机离线时的处理（倾向：请求 TTL 内目标上线仍可确认，需后端队列语义确认——实现时若超出 TTL 则拒绝并提示）。
