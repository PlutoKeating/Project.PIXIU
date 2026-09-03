# D-07 效果与测试报告工作稿

- 更新日期：2026-09-04
- 状态：portable 开发基线已有；最终 V11 双 SDK/Agent/三设备报告未完成

## 测试口径

最终报告按 H-01～H-03、A-01～A-14、F1～F7、P-01～P-04、N-01～N-08 和
R-01～R-06 分层。每组结果记录 release commit、机器、V11 版本、架构、SDK/runtime、
数据集版本、冷热口径、样本数、原始输出和失败样本。

D-07 的 `原始证据.zip` 由 `submission/build_evidence_archive.py` 生成，不能手工塞入
若干日志即宣称完整。策略要求双 SDK、完整 Agent 生命周期、最终性能、三设备总报告、
安装升级矩阵、数据集清单和 Agent 供应链七类主记录全部通过并绑定同一 commit/候选
包摘要；附件中的 CSV、日志和截图均进入逐文件摘要，文本附件还接受敏感信息扫描。

## 已有开发基线

单一版本源回归动态读取根 `VERSION`，核对前端 CMake、独立 control、发布脚本、
Module E 模板和成包 manifest 的派生关系，并拒绝显式版本漂移；成功路径不再写死
当前发布号，后续正常升版只需修改一个输入文件。
包外资产清单测试使用临时 `.deb`/checksum/signature，验证版本、架构、通道、commit、
三个资产的大小与 SHA-256、确定性时间、篡改包及无效主包签名拒绝；Release/publish
接线还会校验包内 commit/版本/架构、拒绝输出覆盖输入、记录规范化生成命令，并为
清单本身生成 checksum 和 Ed25519 签名。最终报告仍须用最终候选六件套
复验并归档原始输出。
分阶段门禁测试覆盖 generic 放行、strict 的 Kylin V11/架构成功与拒绝、构建期
KYSDK/strict 错配拒绝，以及用户态 Agent/runtime 缺失、版本命令失败、非 0.9.x、
歧义版本输出拒绝；失败发生在 Provider 目录写入前。实际 generic `.deb` 控制归档已
确认 `STRICT_NATIVE=0`。双 SDK 包依赖和后端 strict 预检已有独立测试；最终严格包仍须
在目标 V11 保存完整真实结果。
原生取证器单测另验证：非严格 manifest 必须拒绝；成功证据绑定候选包摘要/commit、
并固定声明 `kylin-v11-native-sdk-product-lifecycle` 类型、真实设备属性和通过状态，
包内与已装 manifest、dpkg 的 PIXIU/双 SDK 版本、Agent runtime 和三个端点；隔离集合
直接执行 LoadDBFile/create/load/upsert/search/delete/drop/disconnect，产品 API 另走
写入/召回/遗忘且失败时清理数据库与集合。该测试只证明取证器逻辑，不能替代目标
V11 的真实输出。
取证器随后修正运行端点组件标识为实际的 `pixiu-memory-backend`，并强制把已安装的
`/usr/lib/pixiu` 放到导入路径首位，避免工作副本源码遮蔽候选包；对应 7 项单测通过。
提交 `ea92b28` 已在 V11 amd64/Python 3.12 按 strict profile 完成 `KYSDK=ON` 构建：
前端 ctest 38/38，Embedding 与 Vector Engine 两个 cp312 扩展均链接并进入 `.deb`，
包内 manifest 为同一 commit、amd64、strict=true。该构建关闭 wheels 且未安装运行，
只计原生编译/链接切片，不计 H-02/H-03 或最终安装通过。

首次 strict 安装运行得到预期失败证据：官方 AI runtime socket 以桌面用户 UID 隔离，
专用系统服务账户没有对应 runtime，后端严格预检拒绝就绪并进入重启；恢复 portable
配置后健康检查重新通过。AI 子系统升级到 runtime `1.2.0.4` 不改变该安全边界。
因此当前缺口不是“再装一个 SDK 包”，而是 W2.6 用户会话 SDK 边界；解决前不得把
失败关闭或直接桌面用户调用冒充产品 H-02/H-03 闭环。
继续隔离诊断发现两个更具体的问题：Vector 客户端使用了官方头文件标为测试用途的
host/port 构造，因而错误连接未监听的 `127.0.0.1:19530`；现已改用官方 demo 的
`ConnectParam(appId)` 并增加契约测试。Embedding 在 ABI 修复后已连接 runtime
1.3.0；原系统组件组合因缺少 `model_catalog` 导致 `getModelList` err=3、显式
初始化 err=10。官方 `kylin-ai-runtime` `devel/26w` 提交
`34843d14363a1c1dff932a9a1cf9b4f09ea75de2` 的
`LifecycleAwareEmbeddingEngine::parseModelInfo()` 明确要求对象型 `model_catalog`，
并从 `TEXT`/`IMAGE` 目录建立模型组。官方 embedding engine `3fbfeb6` 与
abstract-models/model_bank `b999d89`（首个包含标签 `build/1.2.0.0-0k0.16`）补齐
上下游目录契约；兼容性构建后，官方 demo 与 PIXIU 安装包内 binding 均返回
gte-base 768 维非零向量、错误码 0。该手工对齐不是最终依赖交付，H-03 状态不变。

随后提交 `4011d0d` 的 strict revision 7 修正本地连接并补齐数据库生命周期：前端
ctest 38/38、双原生扩展链接及包安装通过；Vector Engine direct SDK 使用独立临时
数据库和固定 4 维测试向量完成 LoadDBFile/create/load/upsert/search/delete/
deleted-hidden/drop/disconnect，全部返回 passed。该成功记录没有调用 Embedding 或
产品 API，因此只计 W1.1 底层 SDK 实证，H-02/H-03 仍保持不通过。

portable 自建数据集记录为偏好 100%、知识召回 100%、冲突 96%、P95 115ms；它只
证明通用路径可回归，不能证明 H-01～H-03。2026-09-04 最新组合回归为 Foundation
636 项、Engine 154 项、Module E 19 项（合计 pytest 809 passed），最近前端 ctest
38/38；Python 回归报告有 10 条既有依赖弃用告警但无失败。新增安装健康
切片另由 7 项单元测试及发布 helper 脚本覆盖。提交最终稿前仍必须从
同一候选 commit 重新运行并保存原始日志。

同日还修复了升级停服风险：`SyncRuntime.stop()` 原先只设置调度停止事件，却会等待
当前 mDNS/反熵/对端请求完整超时；现改为取消当前调度任务、等待协程清理并关闭
discovery/TLS server。永久阻塞轮次的有界停止测试通过；当前 Foundation 636 项回归通过；
目标 V11 安装包的实际 systemd 停止时长仍须随下一候选重验。

同一轮 Python 3.14 全量回归曾捕获 aiosqlite 工作线程在事件循环关闭后回调的 teardown
告警。根因是应用 lifespan 从未关闭全局异步数据库，且 strict 启动在进入原清理段前
即可失败。当前生命周期已把全部启动纳入 `try/finally`，在其他 runtime 停止后幂等
关闭数据库并失效 DB 绑定服务；将 `PytestUnhandledThreadExceptionWarning` 提升为错误
的 Foundation 636 项回归通过；完整组合回归保留 10 条既有依赖弃用告警。

三节点同步协议回归新增离线遗忘防复活场景：A/B/C 全互信并收到初始共享值后，C
离线错过 B 的删除墓碑；重连时通过摘要差集补齐墓碑，三方收敛到删除状态。初始创建
op 在回收前重复重放均被拒绝；A 只有收到 B、C 两个活跃 peer 的墓碑 ACK 才允许回收，
回收后同一旧 op 再次到达仍不会恢复状态。该测试连同原有并发、丢包、乱序、反熵与
撤销用例为 7/7 通过，属于单进程三数据库的协议证据，不计三台 V11 最终通过。
对应 `sync_evidence` CLI 现把五类场景、拓扑、节点 oplog/逻辑视图摘要、release commit
和产品版本写为 JSON，同时固定 `final_device_evidence=false` 与限制列表；该报告可进入
协议回归附件，但不得进入真机证据栏。
Python 3.12 CI 现自动生成该报告，复核 commit、三节点逻辑视图一致、全部场景通过及
`final_device_evidence=false` 后，以 `pixiu-sync-protocol-evidence-<commit>` 上传；
该自动资产减少手工转录，但不会改变其“协议模拟”证据等级。

真实设备拓扑另有两阶段机器证据契约：每台 V11 节点通过
`build/release/scripts/three-device-evidence.py capture` 绑定本机 strict SDK 证据和
loopback 同步状态，并只输出按 run 加盐的身份/域摘要；`validate` 要求三份清单同
候选包、commit、版本、架构与 Agent Runtime，三个身份互异且相互完整可见、全在线、
队列归零、采集窗口不超过 300 秒。当前工具测试 12/12 通过，尚未输入三台真实设备数据；
合并结果固定 `final_device_evidence=false`，必须继续补五项跨设备场景后才进入最终栏。
并发更新取证现新增 3×3 检查点契约，绑定拓扑/节点清单并验证共同基线、两个暂停
节点的不同 v+1 分支、观察节点未变化及恢复后的三端一致。尚无真实三机输入，输出
仍固定非最终证据，不能将 N-04 改为通过。
离线写入/重连取证也采用 3×3 检查点：隔离端保留基线，其余两端在仅两个在线成员时
完成 v+1 写入传播，恢复后隔离端追平，最终三端在线静默。该契约关联 N-02/N-03/N-05，
但同样没有真实三机输入，不能据工具单测修改验收状态。
私域不传播取证新增 3×baseline + 3×post-write：仅写入端必须命中 `user:*` 目标，
两观察端保持零命中，三端待发均为零且各自同步确认计数前后不变。该契约关联 N-06，
仍须真实三机执行。
墓碑取证新增四阶段 12 份检查点，绑定 Agent 可见性及去载荷 CRDT tombstone/clock/op
摘要；旧副本重连和追加反熵后都必须保持同一墓碑，状态缺失不计通过。该契约关联
N-07，同样尚无真实三机输入。
最终汇总门要求四类报告夹在初始与全新收尾拓扑之间，并校验同一候选版本、run、
三身份和共享域；只有汇总结果可标记最终证据。取证工具当前 14/14 通过，真实总报告
尚未生成。提交打包器 4/4 测试进一步验证总报告必须匹配 release commit 和最终
`.deb` SHA-256，畸形或不完整 JSON 会 fail closed。
同步物化回归另核验远端共享知识首次到达即生成向量、同 ID 更新后向量发生变化、墓碑
到达后向量删除；快进与自动语义仲裁均由生产 DI 注入 `KnowledgeService`，不再只更新
SQLite/FTS。该项仍需在最终 V11 系统 Vector Engine 上复验，不能由 portable 测试替代。
knowledge 早于 evidence 分批到达的回归现验证：先以无悬空外键状态物化并持久登记
待补引用，后续 evidence 到达后自动补链且待办清零，避免 Agent 上下文永久失去 citation。
shared 本地冲突写入回归另验证：MERGE 后 oplog 的 knowledge 载荷等于最终持久化正文，
且 version 为 2，而非仲裁前输入；因此发送端业务视图与待传播状态不会立即分叉。

同用户产品 API 探针随后发现旧包只创建 Vector 客户端、未执行 `LoadDBFile`：能力端点
可误报双 SDK ready，但 `/memory/write` 以 local storage not found 失败。当前源码已
加入 `PIXIU_VECTOR_DB_PATH`、strict 启动实际装载、进程级 store 复用和退出断开；
当前 809 项组合回归通过。提交 `6f6002e` 的 strict revision 8 随后完成 V11 同用户
`/memory/write`、向量召回、两阶段遗忘和删除后隐藏；能力端点报告 V11 与双 SDK
runtime 均 compliant。正式取证器在检查到目标系统缺少 `kylin-agent` 与
`agent-runtime` 可执行文件时按门禁拒绝生成最终证据，因此该记录不计完整 Agent 或
release-ready。

无模型 Agent 集成探针随后通过：官方 0.9.6 宿主在 V11 启动，固定 Runtime Gateway
返回健康，空会话 API 返回列表，Module E 被发现并配置为 `memory.provider=pixiu`。
该探针同时发现官方 0.9.7 ABI 不兼容、公开标签不可重建宿主、Runtime `web` extra
漏装 `aiohttp` 及三重版本元数据漂移；故只证明 ADR-0001 架构可行，不计完整 Agent、
安装或发布通过。

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
