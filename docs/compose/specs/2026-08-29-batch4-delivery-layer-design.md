# 批次④ · 递送层（洞察流 / 定时简报 / 相关性提醒）Design Spec

> 日期：2026-08-29 · 状态：待规划
> 定位：被动监控四批次路线的收官——把「一次配置、永久监控」沉淀的记忆转化为**主动递上**：像助手一样在用户需要时默默递上最相关的内容/服务/提醒，兑现产品愿景的「主动服务」半句。

## [S1] 背景与目标

- 批次①-③已完成：监控掌控层（开关/面板/徽标）、目录监视闭环（capture_event 实时事件）、行为采集+偏好对齐（preference_accuracy 1.0）+ 冲突分级打扰。记忆库里已有真实沉淀（目录文件/OCR/文本 evidence + 结构化 knowledge）。
- 缺口：**没有任何主动输出**——所有能力都是「用户问才答」。愿景要求「能力供给在用户任何需求的情况下，像助手一样默默递上用户最需要的内容、服务、体验、提醒或数据」。
- 本批次目标：三种递送形态的最小可行闭环——**洞察流**（进入聊天窗时按偏好/热度递上相关内容）、**定时简报**（每日/定时汇总当日记忆沉淀）、**相关性提醒**（基于当前活跃上下文/目录事件的即时轻提醒）。

## [S2] 三种递送形态

### [S2.1] 洞察流（聊天窗欢迎页动态建议）
- 现状：`ChatWindow` 欢迎页 `buildWelcomeView()`（suggestionCard 建议卡）为静态文案。
- 改造：打开聊天窗/回欢迎页时拉取 `GET /delivery/insights?limit=3` → 渲染动态建议卡（标题+一句话摘要，点击 → 触发对应检索/打开记忆面板）。
- 服务端生成规则（后端 `backend/foundation/api/delivery.py` + `backend/engine/delivery/insights.py`）：
  - 候选：最近 24h 入库的 knowledge（按 quality_score 降序）+ 偏好 resolve 命中的「高频工具」提示；
  - 过滤：sensitivity>0 不出现；已有 source=sync 的 MANUAL 冲突待处理时不递送相关候选（避免干扰人工裁决）；
  - 输出：`{"insights": [{"title", "summary", "knowledge_id", "score", "kind": "recent|preference"}]}`；summary 服务端生成不含敏感原文。

### [S2.2] 定时简报（每日摘要）
- 后端：`backend/engine/delivery/digest.py`——按日聚合（当日 ingested capture_event 数量按 source 分组 + 偏好变化 + 冲突裁决情况），生成中文简报文本；
- 触发：`GET /delivery/digest?date=YYYY-MM-DD`（按需拉取）+ 前端「今日简报」入口（悬浮球菜单或聊天窗建议卡）；
- 输出：`{"date", "summary": "今日新增 12 条记忆（目录 8、文本 3、剪贴板 1），2 项偏好更新，1 项冲突已自动合并。"}`；
- 简报由服务端生成用户可读文案，不含敏感原文全文。

### [S2.3] 相关性提醒（即时轻提醒）
- 触发源：目录监视 capture_event（批次②已有 WS 广播）+ 行为采集（批次③）——
  - **目录事件提醒**：新文件入库（ingested）时若与最近 24h 高频关注主题相关（简单关键词交集：文件名 token vs 近期 knowledge title token），弹轻提醒「已记住 文件 X（与您近期的 Y 相关）」；
  - **偏好提醒**：偏好变更（版本升级）时轻提醒「已学习您的偏好：X」；
- 实现：前端在既有 captureEvent/偏好事件路径上做**相关性判断**（轻量：文件名/标题 token 交集，不引入新后端服务）；`sensitive_quarantined` 维持批次②既有通知语义。
- 节制原则：相关性提醒每类每天上限（如 3 条），避免打扰；悬浮球角标聚合未读数。

## [S3] 契约（docs/API.md 新增）

- `GET /delivery/insights?limit=3` → `{"insights": [{title, summary, knowledge_id, score, kind}]}`（runtime 未启动/空库 → `{"insights": []}`）；
- `GET /delivery/digest?date=YYYY-MM-DD` → `{"date", "summary"}`（空日 → summary 为「当日无新记忆」）；
- 错误契约沿用既有 `{error, message, request_id}`；limit 缺省 3、上限 10（>10 → 400 INVALID_REQUEST）。

## [S4] 测试策略

- 后端 pytest：
  - insights：最近 24h 排序、sensitivity 过滤、MANUAL 冲突抑制、kind 区分、空库/空列表；
  - digest：按日聚合计数正确、文案不含敏感原文、空日文案；
  - API：端点契约（limit 校验、错误体、空列表）；
- 前端 ctest（offscreen）：
  - 欢迎页动态建议卡渲染（FakeTransport 注入 insights 响应）；
  - 建议卡点击触发检索；
  - 目录事件相关性提醒（同主题触发 / 不同主题不触发 / 每日上限）；
  - 偏好变更提醒；
- 全量回归：后端全量 pytest + `frontend/scripts/regression.sh`（OFF/ON 双路径）。

## [S5] 范围边界（不做）

- 不做推送通道（仅应用内通知/悬浮球角标，无系统级 Push/短信/邮件）；
- 不做 LLM 生成摘要（简报/洞察为规则化模板，无大模型依赖——离线可运行）；
- 不做跨设备递送（递送是本地行为，同步批次已处理跨设备记忆）；
- 不引入定时器常驻任务（简报为按需拉取；「每日自动推送」留待未来——避免 daemon 常驻调度复杂度）。

## [S6] 风险与开放点

- 相关性提醒的「相关」判定用 token 交集可能误报/漏报——MVP 可接受，阈值可调；
- 洞察流排序的质量分（quality_score）在真实数据下的分布未知——先按降序取 top3，后续可用偏好加权；
- 前端欢迎页建议卡改造需保持 offscreen 测试稳定（QSignalBlocker/无网络依赖）；
- 与批次② captureEvent 既有处理（角标+活动记录+隔离通知）的叠加——提醒只新增「相关主题」轻通知，不改变既有行为。
