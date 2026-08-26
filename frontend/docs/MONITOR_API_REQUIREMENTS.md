# 监控引擎 API 契约需求单（Module A → Module B/C）

> **来源**：产品愿景「一次配置，永久监控」掌控层批次①落地后的批次②前置需求。
> **状态**：⬜ 待 Module B/C 评审实现；本文档为前端消费方的期望契约，
> 最终以 `docs/API.md` 双方确认为准。
> **范围**：监控配置读写、活动日志查询、WS 实时捕获事件三类契约，以及
> 前端现有实现的衔接方式。Module A 未修改任何 `backend/` 文件。

---

## 1. 配置读写

### GET /monitor/config

读取当前监控配置（daemon 视角的全量状态）。

- **成功响应** `200`：

  ```json
  {
    "enabled": false,
    "sources": {
      "directory": false,
      "clipboard": false,
      "behavior": false,
      "screenshot": false
    },
    "directories": ["/home/u/Downloads"]
  }
  ```

- **字段说明**
  - `enabled`：全局总闸。关闭时所有数据源停止捕获（各数据源开关状态保留）；
  - `sources`：四类数据源开关，键名固定为
    `directory | clipboard | behavior | screenshot`，与前端
    `MonitorSource` 枚举一一对应；
  - `directories`：监视目录绝对路径清单，去重、非空。

### PUT /monitor/config

写入监控配置，请求体结构与 GET 响应一致（全量提交，不做局部 patch）。

- **行为要求**：服务端持久化配置，并对运行中的 daemon **热生效**
  （开启/关闭对应采集器、增删 inotify 监视点），无需重启 daemon；
- **错误响应** `400 INVALID_REQUEST`：未知 source 名、字段类型错误、
  目录路径为空等；错误体沿用既有错误结构（`code` + `message`）。
- **验收建议**：PUT 后立即 GET 应返回新值；重启 daemon 后配置不丢失；
  对 daemon 进程存续期间的开关切换，采集器行为即时变化。

---

## 2. 活动日志

### GET /monitor/log?limit=100&offset=0

分页查询监控活动记录（按时间倒序，最新在前）。

- **成功响应** `200`：

  ```json
  {
    "events": [
      {
        "ts": 1756080000,
        "source": "directory|clipboard|behavior|screenshot|system",
        "status": "ingested|sensitive_quarantined|ignored|state_changed",
        "summary": "记住文件 支出清单.xlsx",
        "evidence_id": "evd_...",
        "knowledge_id": "knw_..."
      }
    ]
  }
  ```

- **字段说明**
  - `ts`：Unix 秒时间戳（与前端 `MonitorLogEntry::timestamp` 同单位）；
  - `source`：比数据源多一个枚举值 `system`，承载监控自身状态变更
    （如总闸开闭、daemon 启停）；
  - `status`：`ingested` 已入库 / `sensitive_quarantined` 敏感隔离 /
    `ignored` 忽略 / `state_changed` 状态变更；
  - `evidence_id` / `knowledge_id`：关联的证据与知识条目 ID；事件未产生
    入库时允许缺失或为 null（如 `ignored`、`state_changed`）。

- **约束**：`summary` 由服务端生成用户可读中文文案（如「记住文件 支出清单.xlsx」），
  **不得包含敏感原文全文**——隔离类条目只给脱敏摘要，避免日志本身成为泄露面。
- **验收建议**：`limit`/`offset` 分页正确；`limit` 缺省 100；空日志返回
  `{"events": []}` 而非 404。

---

## 3. WS 实时事件（`/events` 新增业务事件类型）

在 `docs/API.md §4` 既有四类业务事件之外，新增 `capture_event`：

```json
{
  "event": "capture_event",
  "data": {
    "source": "directory",
    "status": "ingested",
    "summary": "记住文件 支出清单.xlsx",
    "ts": 1756080000,
    "evidence_id": "evd_..."
  }
}
```

- **帧结构**：沿用 `{"event": "...", "data": {...}}` 外壳；`data` 字段与
  §2 日志条目同构（可缺 `knowledge_id`，以事件发生时刻为准）。

- **前端行为映射**
  - 普通事件（`ingested` 等）：角标 +1（可选）、监控中心「活动记录」实时追加；
  - `sensitive_quarantined`：除追加记录外，额外弹系统通知提示用户有内容被
    隔离（隔离区查看与恢复交互属批次③范围，本批次只做通知触达）。

---

## 4. 行为边界

- **配置生命周期**：daemon 关停时配置仍持久（落盘）；前端离线时展示本地
  缓存的上次已知配置并明确标注「离线」，不做静默降级为默认值。
- **敏感度判定单一来源**：是否敏感沿用写入链路既有 detector 判定，
  监控链路不得另起一套规则；判定为敏感的捕获走 `sensitive_quarantined`。
- **隔离条目不出域**：`quarantined` 条目不入 `shared:*` 共享域，
  不参与任何同步/流转，仅在本机可见。
- **验收建议**：关停 daemon → 改动本地文件 → 重启 daemon，确认期间事件
  补齐或至少不丢配置；构造敏感样本确认走 detector 隔离而非入库。

---

## 5. 与前端现有实现的衔接

批次①已落地纯本地实现，批次②在其上扩展远端契约：

- **已有资产**
  - `frontend/src/app/MonitorController.{h,cpp}`：全局开关 + 四类数据源
    开关 + 监视目录清单，经 AppSettings 键 `app/monitor/enabled`、
    `app/monitor/source/<name>`、`app/monitor/directories` 本地持久化；
    活动日志目前为内存级（重启清零），只记录本机状态变更；
  - `frontend/src/widgets/MonitorCenterDialog.{h,cpp}`：Tab1 数据源开关矩阵 +
    Tab2 活动记录列表，直接读写注入的 MonitorController。

- **批次②改造方向**：transport 扩展为**优先远端契约**（HTTP REST +
  WS 推送），本地 AppSettings 键退化为**离线缓存回退**——后端不可达时
  UI 仍可展示与编辑上次同步的配置，恢复连接后再对账。

- **BackendTransport 新增方法签名期望**
  （`frontend/src/services/BackendTransport.h`，异步请求 + 信号回包，
  与既有 `preferencesList()` 等模式一致；基类提供默认空实现，
  测试桩与非 HTTP 传输无需强制实现）：

  ```cpp
  // GET /monitor/config → configResult(config)；失败走 errorOccurred(code,...)。
  virtual void monitorConfig();
  // PUT /monitor/config（payload 即 §1 请求体）；成功同样经 configResult 回包。
  virtual void updateMonitorConfig(const QJsonObject &payload);
  // GET /monitor/log?limit=&offset= → logResult(events)。
  virtual void monitorLog(int limit, int offset);

  signals:
  void configResult(const QJsonObject &config);   // 含 400 时由 errorOccurred 报告
  void logResult(const QJsonArray &events);
  ```

- **WS 事件路由**：`capture_event` 经既有
  `frontend/src/app/EventRouter`（`backendEvent` → `handleEvent`）扩展分发，
  新增语义信号 `captureEvent(const QJsonObject &data)`；未知/残缺帧继续
  按「安全忽略」处理，不断连、不崩溃。UI 层只订阅语义信号，
  不感知 WS 原始 payload。

---

## 备注

- 本文为前端单方面期望稿；`docs/API.md` 相关章节由 Module B/C 评审后
  补充，双方确认前前端不合并依赖 `/monitor/*` 的功能分支。
- 待评审澄清项：`limit` 上限、`ts` 是否需要毫秒精度（当前按秒设计）、
  `capture_event` 是否需要断线补发（当前假设不补发，离线期事件靠
  §2 日志查询兜底）。
