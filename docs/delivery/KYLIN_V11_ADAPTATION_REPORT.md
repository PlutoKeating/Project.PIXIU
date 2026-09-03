# D-10 银河麒麟 V11 适配报告工作稿

- 更新日期：2026-09-03
- 状态：历史麒麟 V11/桌面基线存在；最终 Agent + 双 SDK + 安装升级取证未完成

## 已确认基线

仓库已有 V11 x86_64 profile、`.deb` 构建/安装、systemd 后端、Qt/UKUI 桌面入口、
KYSDK 开关和 Debian 降级路径记录。历史环境为 Python 3.12.3、Qt 5.15.19；这些
记录不能替代最终候选版本的重新验证。

2026-09-03 的脱敏平台探测确认 x86_64 目标使用 `VERSION_ID=V11` 格式；能力端点和
原生 CI 已兼容 `11`、`V11`、`v11` 三种写法。刷新当前配置的软件源后，双 SDK、
桌面 KylinSDK 及其开发包均无安装候选，因此本轮只能确认平台识别，不能执行或宣称
双 SDK 原生验收通过。后续须在提供这些官方包和 Vector Engine/AI runtime 的 V11
环境重新运行 strict workflow；不得以源码语法编译或 portable 结果替代。

## 最终适配矩阵

| 项目 | x86_64 | arm64 | 必须证据 |
|------|--------|-------|----------|
| V11 图形安装/卸载 | portable 跨 revision、离线依赖、helper 健康已重验；图形/卸载待验 | 待真机 | 系统/架构、安装器、包日志 |
| openKylin Agent + Module E | 未完成 | 未完成 | 版本、provider 加载、完整 run |
| Embedding SDK | 待最终证据 | 待真机 | runtime、调用日志、严格失败 |
| Vector Engine SDK | H-02 未通过 | H-02 未通过 | 建库/写入/查询/删除与进程证据 |
| UKUI/KYSDK | 历史基线 | 待真机 | 快捷键、通知、主题、DPI/多屏 |
| GUI 一键升级 | 固定公钥验签及安装健康已接线；正式签名资产与完整门禁待验 | 待真机 | 坏签名、授权、健康失败、回滚、受控重启 |
| 资源与性能 | 待双 SDK | 待双 SDK | CPU/RSS/磁盘/带宽/P50/P95 |

最终报告必须列出目标镜像/内核/桌面、系统包和 SDK 版本、profile 差异、已知问题、
降级行为及解决记录。任何 `KYSDK=OFF`/portable 结论单独成表，不标为原生验收。

### 2026-09-03 portable 安装升级回归（非原生 SDK 验收）

- 提交 `30e0d64` 在 Kylin V11 amd64 目标环境完成本地构建，前端 ctest 37/37；
- `.deb` 携带完整 cp312 离线 wheels，`0.1.7-3` 到测试 revision `0.1.7-4` 的
  非交互跨 revision 升级成功，包内 helper 同版重装及安装健康检查通过；
- `/etc/pixiu/pixiu.env` 升级前后 SHA-256 一致，配置与随机同步口令未被覆盖；
- 核心数据逻辑计数摘要保持一致，后端报告产品 `0.1.7`、schema 12、数据库 ready；
- `pixiu-backend.service` 为 active，`GET /capabilities` 正确识别 Kylin V11；
- Embedding/Vector runtime 均为 `portable`、`contest_ready=false`，因此只计安装兼容
  回归，不计 H-02/H-03 或最终性能验收。
