# Module C · Phase 3 同步实现报告

## 1. 交付范围

Phase 3 完成 Module C 的去中心化共享记忆基础设施：

- Ed25519 设备身份，私钥以口令加密 PKCS#8 持久化。
- QR/PIN 签名配对令牌、公钥交换、有效期与 nonce 防重放。
- LWW-Element-Set、版本向量、确定性并发收敛。
- 持久化 oplog、按 peer ACK、离线重传、digest/delta 反熵。
- 全部活跃 peer ACK 后的 tombstone 延迟回收。
- mDNS 局域网发现、已配对 peer 信任过滤。
- TLS 1.3 双向证书传输、1 MiB 帧上限、每批 256 个操作。
- Gossip 有界 fanout、失败离线标记与指数退避调度。
- CRDT 胜者向 evidence、knowledge、preference 仓储物化；knowledge 生产路径复用
  `KnowledgeService` 重建图/embedding/VectorStore，墓碑删除向量。
- /sync/pair、/sync/peers、/sync/status、/sync/peers/{id}/revoke。
- shared:* 写入自动追加签名 SyncOp，共享遗忘追加 knowledge tombstone。

本阶段没有进入 eval/ 或 D-Bus，未修改 backend/engine/。

## 2. 数据与收敛

Schema 从 v3 升级到 v4。基础表由 11 张增至 16 张，新增：

- sync_identity：单例设备身份、加密私钥与公钥。
- sync_peers：配对状态、公钥、最后在线/同步时间。
- sync_state：每个逻辑实体的 CRDT 物化状态。
- sync_peer_acks：peer 对操作的幂等 ACK。
- sync_meta：配对 nonce、最近反熵时间等元数据。

本地共享写入顺序为 evidence → knowledge → preference。每个操作包含 scope、origin、
版本向量和 Ed25519 签名。远端先对整批操作做结构、域、信任关系和签名校验，再按
vclock 判断因果关系；并发或相同因果上下文按 (ts, op_id) 决胜，同时合并所有已见
版本向量，保证不同到达顺序得到相同结果。

## 3. 安全边界

- 网络默认开启（SN-4 起，`config.py` 对 `PIXIU_SYNC_NETWORK_ENABLED` 缺省 true）；
  显式 `false` 或运行时 `enabled=false` 时停止监听、mDNS 与连接；缺 advertise 地址
  由 runtime 自动取本机 LAN IP（回退 loopback 并告警），缺 TLS 证书由 di 层降级
  （log warning，不阻塞 API）。
- 仅 shared:* 可进入 oplog；user:* 会被拒绝，payload 内嵌 scope 也必须与 envelope 一致。
- mDNS 广告不是信任来源。只有本地已配对、未撤销、同域且 Ed25519 公钥完全一致的广告可用。
- 地址只接受私网、链路本地或 loopback；全局公网、multicast 和 unspecified 地址被拒绝。
- 传输只允许 TLS 1.3，客户端和服务端都要求受信 CA 证书并校验服务端主机名。
- Wire 协议只接受 push，不向请求方暴露本地摘要或记忆内容；每个 SyncOp 仍须独立验签。
- pairing token 最大 16 KiB、最长 900 秒；PIN 使用 PBKDF2-SHA256 200,000 轮摘要。
- 私钥、口令、真实证书和真实网络地址不写入仓库。

## 4. 运行时

FastAPI lifespan 调用同步运行时；默认开启（`PIXIU_SYNC_NETWORK_ENABLED` 缺省 true，
SN-4），显式置 false 或运行时 `enabled=false` 时不再启动。一个同步轮次执行：

1. mDNS 发现候选端点。
2. 用持久化配对记录过滤候选。
3. 把可信 peer 标记为在线。
4. 从 oplog 选取该 peer 未 ACK 的同域操作。
5. 经 mTLS 推送并记录有效 ACK。
6. 失败 peer 标记离线；调度器按有界指数退避重试。

配置项和证书准备方式见 backend/foundation/docs/QUICK_START.md。

## 5. 验证

开发与回归均使用 Anaconda pixiu（Python 3.10.20）：

~~~bash
conda activate pixiu
python -m pytest backend/foundation/tests backend/engine/tests -q -ra
~~~

结果：310 passed, 1 warning，其中 Foundation 289 项、Engine 21 项。唯一 warning 为
既有 Starlette TestClient/httpx 弃用提示。

同步专项覆盖：

- 身份加密、签名、错误口令。
- QR/PIN 配对、篡改、过期、跨域、重放。
- vclock/LWW 收敛、批次先验签。
- 反熵、ACK、离线重传、墓碑回收、调度退避。
- mDNS 广告解析、公网地址拒绝、配对记录/公钥/域过滤。
- 内存协议与 Gossip；不访问真实局域网。
- 仅 127.0.0.1 的 TLS 1.3 mTLS 成功路径和无客户端证书拒绝路径。
- shared 写入入队、user 写入零入队、远端物化与共享遗忘墓碑。

## 6. 环境验收待办

当前 Windows 开发机没有执行真实局域网扫描或跨设备连接。以下项目留给银河麒麟设备验收：

- 两台真实设备的 mDNS 可见性和防火墙策略。
- 真实 CA/证书轮换、SAN/主机名配置和吊销流程。
- 断网、重连、长时间离线后的最终一致性。
- 多设备并发、吞吐、资源占用和 tombstone 保留周期。
