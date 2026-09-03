# D-10 银河麒麟 V11 适配报告工作稿

- 更新日期：2026-09-04
- 状态：V11 双 SDK 产品链与无模型 Agent 宿主链已有强实证；最终供应链、模型运行和安装升级取证未完成

## 已确认基线

仓库已有 V11 x86_64 profile、`.deb` 构建/安装、systemd 后端、Qt/UKUI 桌面入口、
KYSDK 开关和 Debian 降级路径记录。历史环境为 Python 3.12.3、Qt 5.15.19；这些
记录不能替代最终候选版本的重新验证。

脱敏平台探测确认 x86_64 目标使用 `VERSION_ID=V11` 格式；能力端点和原生 CI 已兼容
`11`、`V11`、`v11`。2026-09-04 软件源已提供并安装双 SDK、桌面 KylinSDK 及开发包；
提交 `ea92b28` 完成 strict 原生编译。首次 strict 安装运行进一步确认 AI runtime
socket 按 UID 隔离，当前专用系统服务账户无法复用桌面用户会话 runtime，后端因此
按 strict 规则拒绝就绪；恢复 portable 配置后服务重新健康。该结果只证明失败关闭，
该旧结果已被 revision 8 同用户双 SDK 产品链实证推进，但最终依赖仍未交付化，
不得宣称 H-02/H-03 通过。

## 最终适配矩阵

| 项目 | x86_64 | arm64 | 必须证据 |
|------|--------|-------|----------|
| V11 图形安装/卸载 | portable 跨 revision、离线依赖、helper 健康已重验；图形/卸载待验 | 待真机 | 系统/架构、安装器、包日志 |
| openKylin Agent + Module E | 官方 0.9.6 宿主、固定 Runtime、Gateway 与 Provider 无模型探针通过；供应链/模型 run 未完成 | 未完成 | 可重建源码、版本、provider 加载、完整 run |
| Embedding SDK | revision 8 产品链已使用真实 gte-base 768 维向量；最终依赖/Agent 待验 | 待真机 | runtime、调用日志、严格失败 |
| Vector Engine SDK | revision 8 产品写入/检索/遗忘/隐藏通过；最终 user service 待实现 | H-02 未通过 | 建库/写入/查询/删除与进程证据 |
| UKUI/KYSDK | `KYSDK=ON` 构建及 ctest 38/38；桌面实操待验 | 待真机 | 快捷键、通知、主题、DPI/多屏 |
| GUI 一键升级 | 签名/健康及跨 revision 事务回滚已验；受控重启源码/包结构已测；完整门禁待验 | 待真机 | 图形授权、最终候选回滚与重启后全链路 |
| 资源与性能 | 待双 SDK | 待双 SDK | CPU/RSS/磁盘/带宽/P50/P95 |

最终报告必须列出目标镜像/内核/桌面、系统包和 SDK 版本、profile 差异、已知问题、
降级行为及解决记录。任何 `KYSDK=OFF`/portable 结论单独成表，不标为原生验收。
原生工作流已接入脱敏取证器：在隔离 Agent profile 中激活 Provider，绑定严格候选包
摘要/commit、已装 manifest、dpkg 架构与 PIXIU/双 SDK 版本、Agent runtime 和三个
运行端点，再以唯一临时集合直测 SDK 全生命周期并清理。当前仅完成脚本及隔离测试，
尚无最终候选的目标 V11 输出。
取证生命周期已补齐官方 demo 的 `LoadDBFile` 与 `Disconnect`，数据库放在独立临时
目录并在断开后清理，避免验收数据污染用户的生产向量库。
严格画像的目标构建发现桌面 KylinSDK 与 gsettings-qt 运行包不提供 `pkg-config` 开发
元数据；画像已补入系统仓库确认存在的 gsettings-qt 及 shortcut/notification/
qtwidgets 四个 `-dev` 包；提交 `ea92b28` 的重建已确认这些依赖足以通过前端配置和
两项后端原生扩展链接，但不据此提前更新 H-01～H-03 状态。

### 2026-09-04 strict 原生编译切片（非运行验收）

- V11 amd64、Python 3.12 上按仓库 strict profile 构建成功；
- Embedding SDK/开发包为 `1.2.0.0-0k0.4`，Vector Engine SDK/开发包为
  `1.2.0.0-0k1.1`；
- 前端同时发现 shortcut `3.0.1.0`、notification `3.0.1.0`、qtwidgets `2.3.1.0`
  与 gsettings-qt `1.0.0`，`KYSDK=ON` ctest 38/38；
- `.deb` manifest 绑定 commit `ea92b280e34b5f1377aa959d11a59696a4a07db9`、amd64、
  `kylin-v11-native-x86_64`、`kysdk=ON`、`install_strict=true`，并包含 Embedding 与
  Vector Engine 两个 cp312 原生扩展；
- 本切片关闭离线 wheels 且未安装候选包，未运行 SDK 服务生命周期或完整 Agent，
  因而只证明可编译/链接，不计 H-02/H-03 或最终交付通过。

### 2026-09-04 strict 首次运行切片（失败证据）

- strict 包完成安装，Embedding/Vector 原生扩展随包部署；
- 官方 AI runtime 以桌面用户 UID 创建 Unix socket，`pixiu-backend.service` 的专用
  系统账户没有对应 runtime，严格启动预检失败并触发服务重启；
- portable 配置恢复后 `/health` 返回 ready，组件标识为 `pixiu-memory-backend`；
- AI 子系统随后升级到 runtime `1.2.0.4`，但升级本身不解决跨 UID 边界；
- 子系统升级后需同步升级 `kytensor-client/python/server` 到同源候选版本，否则 runtime
  因 Triton ABI 符号不匹配无法启动；最小升级后 runtime 可正常初始化并重建 socket；
- Vector Engine user unit 升级后经 daemon reload/restart 正常启动；首次 direct SDK
  仍失败是 PIXIU 误用了官方测试专用 TCP 构造，已改为 `ConnectParam(appId)` 待重编；
- Embedding 原系统组合缺少 `model_catalog`，SDK `getModelList` 返回 err=3、显式
  初始化 err=10；对齐官方 embedding engine `3fbfeb6` 与 model_bank `b999d89` 后，
  官方 demo 与 PIXIU binding 均经 runtime 1.3.0 返回 gte-base 768 维非零向量；
- 官方 `kylin-ai-runtime` `devel/26w` 提交
  `34843d14363a1c1dff932a9a1cf9b4f09ea75de2` 的生命周期实现明确要求对象型
  `model_catalog` 并从 `TEXT`/`IMAGE` 目录建立模型组；该契约与目标系统日志吻合，
  当前阻断应按 runtime、引擎和模型包的版本/元数据契约不一致处理，而不是 PIXIU
  侧静默降级或伪造成功；
- 该结果登记为 W2.6 的发布阻断证据。完成用户会话 SDK 边界并在同一候选上重跑
  direct SDK 与产品 API 生命周期之前，H-02/H-03 均保持不通过。

### 2026-09-04 Vector Engine direct SDK 成功切片（非 H-02 最终通过）

- 提交 `4011d0d` 构建 strict amd64 revision 7，两个 cp312 扩展链接成功，前端
  ctest 38/38；包升级安装后 portable 服务恢复 ready；
- 修正生产连接为 `ConnectParam(appId)`，并按官方 demo 补齐 `LoadDBFile` 与
  `Disconnect`；
- 桌面用户会话中以固定 4 维测试向量、独立临时数据库和唯一集合依次通过数据库装载、
  create/load/upsert/search/delete、删除后不可检索、drop、disconnect，退出码 0；
- 临时集合和数据库均由取证器清理；该切片没有调用 Embedding，也没有经过产品
  `/memory/write`/`query`/`forget`，故只关闭 W1.1，不把 H-02 标为通过。

### 2026-09-04 同用户产品探针失败与源码修复（待重建）

- 同用户启动的旧 strict 包能力端点可报告双 SDK ready；
- 第一次 `/memory/write` 因生产组合根未执行 `LoadDBFile` 返回 local storage not found；
- 当前源码已增加 `PIXIU_VECTOR_DB_PATH`，strict 预检实际装载应用数据库，store 在
  进程内复用且退出时 `Disconnect`；当前 797 项组合回归通过；
- 只有重建候选完成写入、查询、遗忘与删除后隐藏，才能升级为 H-02 产品证据。

提交 `6f6002e` 的 strict revision 8 已完成上述产品复验：能力端点确认 V11 与双 SDK
runtime，写入、召回、遗忘、删除后隐藏均通过。正式取证器进一步检查时发现目标系统
没有 `kylin-agent`/`agent-runtime` 可执行文件并拒绝出证；因此宿主供应链、ADR-0002
user service 与最终组件依赖仍是发布阻断。

同日宿主供应链探针确认：官方 0.9.6 amd64 二进制可在 V11 启动并创建用户级
Gateway，`/health` 与 `/api/sessions` 可用，Runtime 发现并选中 PIXIU Provider。
但 0.9.6 公开标签链接缺实现、0.9.5/0.9.4 标签缺源文件，0.9.7 二进制要求目标系统
不具备的 `CXXABI_1.3.15`。此外 Runtime `web` extra 未带 API Server 实际需要的
`aiohttp`，同一提交还有 0.9.4/0.9.8/0.9.9 三项版本事实。以上均纳入 ADR-0003，
不把临时拼接环境计为安装验收。

### 2026-09-03 portable 安装升级回归（非原生 SDK 验收）

- 提交 `30e0d64` 在 Kylin V11 amd64 目标环境完成本地构建，前端 ctest 37/37；
- `.deb` 携带完整 cp312 离线 wheels，`0.1.7-3` 到测试 revision `0.1.7-4` 的
  非交互跨 revision 升级成功，包内 helper 同版重装及安装健康检查通过；
- `/etc/pixiu/pixiu.env` 升级前后 SHA-256 一致，配置与随机同步口令未被覆盖；
- 核心数据逻辑计数摘要保持一致，后端报告产品 `0.1.7`、schema 12、数据库 ready；
- `pixiu-backend.service` 为 active，`GET /capabilities` 正确识别 Kylin V11；
- CI run `33769179956` 的 amd64 签名资产经固定公钥和 helper 验证成功；篡改签名
  在 dpkg 前以退出码 3 拒绝，软件版本和数据摘要不变；
- 提交 `ca35117` 的 CI run `33770727108` 在 amd64/arm64 完成健康失败注入恢复；
  Kylin V11 amd64 从 `0.1.7-4` 尝试安装签名 `0.1.7-1` 后注入失败，helper 以退出码
  5 恢复 `0.1.7-4`；配置、数据库完整性、核心逻辑计数和服务状态保持，临时目录无残留；
- Embedding/Vector runtime 均为 `portable`、`contest_ready=false`，因此只计安装兼容
  回归，不计 H-02/H-03 或最终性能验收。
