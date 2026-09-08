# 监控引擎 API 契约需求单（Module A → Module B/C）

> 状态：现有采集配置、日志和事件契约的前端消费说明，不是所有采集能力通过验收的声明。
> 权威公共接口：根 `docs/API.md`；实际消费方：唯一宿主中的 `PrivacyPage`。
> 本次只按代码事实更新文档，不修改后端实现或增加另一套配置存储。

---

## 1. 配置读写

### GET /monitor/config

读取后端持久化的配置，不是所有采集器实际健康状态。尚未写入时返回总闸关闭、
四个来源关闭、空目录列表：

```json
{
  "enabled": false,
  "sources": {
    "directory": false,
    "clipboard": false,
    "behavior": false,
    "screenshot": false
  },
  "directories": []
}
```

- `enabled` 为采集总开关；关闭不是删除已有记忆，也不构成所有在途写入已取消的证明。
- `sources` 固定键名为 directory、clipboard、behavior、screenshot。
  四个配置键不表示四种采集器都已实现；正式页明确剪贴板和自动截图未实现。
- `directories` 为绝对路径列表，可以为空；字符串去首尾空白、丢弃空串、按原序去重。
  目录存在性、权限和实际监视成功须另外核对。

### PUT /monitor/config

全量覆盖并返回归一化配置，不是 PATCH。客户端应先读取，再发送完整形状：
缺省总开关和来源会补为 false，缺省目录为空；未知顶层键被归一化丢弃。
未知来源键、非布尔开关、非法来源形状、非字符串目录项或相对路径会被拒绝。

错误沿用当前统一结构 `error / message / request_id`，非法请求返回 400，
错误码为 `INVALID_REQUEST`，不再使用旧的 `code` 字段描述 HTTP 错误体。

保存先写 SQLite，再通知订阅者；订阅回调异常会记录而不撤销已经保存的配置。
目录 watcher 的配置应用被调度到其工作线程，目录缺失或监视失败可能只记录日志。
因此 200 或紧接着 GET 一致，只能证明保存结果，不能证明所有采集器即时生效。
成功保存后尝试记录 state_changed 并广播；这两个旁路失败不会把已保存配置变成失败。

正式页保存前要求成功读取完整配置；只改总开关、目录/行为开关和目录列表，
保留读取到的剪贴板/截图字段。失败保留编辑并明确“未确认配置已生效”，
不写第二份 AppSettings 作为产品级配置，也不在重连后自动提交草稿。

---

## 2. 活动日志

### GET /monitor/log?limit=100&offset=0

返回 `{"events": [...]}`，按 ts 倒序、同秒按内部记录 ID 倒序。
limit 默认 100，范围 1–500；offset 默认 0，必须非负；非法分页参数返回 400。
空日志返回 `{"events": []}`，不是 404。

日志项字段：

| 字段 | 当前含义 |
|------|----------|
| ts | Unix 秒时间戳，不是毫秒 |
| source | 来源字符串；system 用于配置等系统状态，不代表一个额外采集器 |
| status | ingested、sensitive_quarantined、ignored、state_changed 等实际状态 |
| summary | 服务端生成说明；目录桥接包含文件名，不能称为已脱敏摘要 |
| evidence_id / knowledge_id | 关联证据/知识标识；未产生入库时可以为 null |

目录摘要不包含文件正文，但文件名本身可能含私人信息；敏感条目也可能带原文件名。
不要公开真实文件名、路径或敏感标识，不把这类原始摘要直接转为系统通知。

文本直读支持 .txt、.md、.csv，默认上限 1 MiB；图片依赖实际 OCR 适配器。
其他后缀、无法读取等情况可能是 ignored，不能以表格文件或空日志猜测 OCR 成功。
敏感捕获仍会入库并携带 sensitivity，使用私有 user:* 范围；“隔离”不等于未保存数据。

---

## 3. WS 实时事件（`/events` 新增业务事件类型）

capture_event 是现有业务事件，不再作为未落地的新增需求。
广播保持 `{"event": "capture_event", "data": {...}}`；
data 含 source、status、summary、ts、evidence_id、knowledge_id。
未产生入库时两个关联 ID 可以为 null。事件传输失败不撤销已经完成的入库或配置保存。

正式路由为 WebSocketClient → BackendEventStatus → PrivacyPage.notifyDataChanged：
标记“采集与隐私”有变化。页面可见、空闲且位于日志首页时合并请求刷新后端日志；
不把 WS 帧直接追加为权威历史，也不增加悬浮球角标。
翻到后续页时不会强制跳回首页；用户可以主动刷新。

WS 没有重放游标。断线重连会提示各页重新核对，不证明期间事件全部补齐；
日志分页也不提供稳定快照，列表新增时 offset 分页可能出现重复或位移。
敏感采集事件没有在当前正式宿主接入额外系统通知或隔离区恢复控件。

---

## 4. 行为边界

- 配置由后端 SQLite 持久化；客户端读取失败不静默覆盖为默认值。
  已加载配置下的草稿可保留，但不代表离线生效或自动对账。
- 配置刷新会替换此页未保存编辑，界面已明确提示；日志刷新不保存配置。
- watcher 使用非递归目录监视。总闸关闭会停止接受相应新事件并清理待处理状态，
  但不能据此保证正在执行的捕获已经撤销，也没有停机期间文件变化全量补扫的保证。
- 敏感判定复用既有 detector。目录桥接只接受私有 user:* 范围，
  不将本机敏感记录直接写入 shared:*；完整同步、流转和泄露边界须另行验证。
- 配置保存、日志记录、证据入库、OCR 识别、跨设备可见是不同层次的证据。
  验收使用唯一合成样本逐项核对，不能互相替代或因超时自动换样本后宣称成功。

---

## 5. 与前端现有实现的衔接

正式界面是 `frontend/management/PrivacyPage.{h,cpp}`，位于“设置 → 采集与隐私”。
旧 MonitorController/MonitorCenterDialog 仍有清退回归，不属于正式运行路径，
也不作为新增功能的扩展基础。

现有异步 transport 契约已实现：

```cpp
virtual void monitorConfig();
virtual void updateMonitorConfig(const QJsonObject &payload);
virtual void monitorLog(int limit, int offset);

signals:
void configResult(const QJsonObject &config);
void monitorLogResult(const QJsonArray &events);
```

HttpBackendTransport 分别消费 GET/PUT 配置和 GET 日志，失败经 errorOccurred 报告。
正式页日志每页请求 50 条；满页允许继续查询，空的下一页是合法结果，不是有总数的证明。
现有列表展示来源、状态和摘要，不应写成已显示时间、证据 ID 或完整原始载荷。
后端关联信息可由公共 API 核对，完整取证界面仍按统一计划补齐。

配置响应必须有完整布尔开关和目录数组才能启用保存；初始化不会自动写默认配置。
读取、保存、日志请求串行；自动日志刷新不会覆盖配置草稿。关闭宿主时
HostCloseGuard 检查在途操作和未保存配置，明确放弃也不会自动提交草稿。

---

## 备注

本文件和根 API 文档按当前代码对齐，保留各自原有章节结构。
接口存在不等于所有系统来源可用；目录权限、OCR 绑定、行为采集降级和关闭竞态
仍需实际平台验证。配置/API 的隔离回归不修改用户真实采集配置或记忆。
