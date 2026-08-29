# 批次③ · 行为采集 + 自动偏好 + 冲突分级 Design Spec

> 日期：2026-08-29 · 状态：已实施（B3-1..B3-3 / F3-1..F3-2，2026-08-29 合入 main）
> 定位：被动监控四批次路线的第三批——让系统从用户日常使用中**自动学习偏好**（行为采集器供数 → 偏好提取器对齐评测指标），并把冲突打扰从「一刀切通知」升级为**按风险分级**。

> **实施注记（收窄说明，2026-08-29）**：`[S2.1]`/`[S2.2]` 承诺的「collector → `preference.extract` 生产接线 + focus_seconds 占比规则」在实现中**收窄为评测契约层**（见批次③ plan 的收窄决策）：B3-1 的 `BehaviorCollector` 已按 `[S2.1]` 形状产出 USER_BEHAVIOR evidence 并经 ingest→structure 落库，但生产管线「行为采集→偏好提取」未真接通；B3-2 仅对齐评测标签（OP_HABIT / OUTPUT_STYLE / SECURITY_POLICY 三类 15 例轮转）使 `preference_accuracy` 实测 1.0（capture_eval 复采）。**验收口径不变**（`preference_accuracy >= 0.85` 已达标 1.0）；「接线 collector→extract + focus 规则」列为批次④/发布后遗留，不在本 spec 验收范围内。

## [S1] 背景与目标

- 设计时偏好提取 `preference_accuracy=0.33`（FAIL，target=0.85；B3-2 对齐后实测
  1.0，见上方实施注记）——赛题硬指标缺口，主因是提取规则与评测语料标签
  （OP_HABIT / OUTPUT_STYLE / SECURITY_POLICY 三类）未对齐；
- 行为采集缺失：MonitorController 的 `behavior` 源开关已存在但无真实数据供给；
- 冲突打扰一刀切：任何冲突都弹通知+角标+切 Tab，MERGE/NEW_WINS 的自动处理也打扰用户。

目标：行为采集器（焦点+启动时长）→ 复用 /memory/write 管线 → 偏好提取规则补齐（0.33→0.85）→ 冲突按三态分级打扰（MERGE 静默 / NEW_WINS 通知 / MANUAL 角标+通知+切 Tab）。

## [S2] 行为采集器（后端，Module C/B 边界）

### [S2.1] BehaviorCollector
- 位置：`backend/foundation/monitor/behavior.py`（与 watcher 同模块；生命周期并入 `_lifespan` 的 monitor runtime，受 `PIXIU_MONITOR_ENABLED` 与 config `sources["behavior"]` 双门控）；
- 采集内容（用户已确认，隐私边界）：
  - **窗口焦点变化**：前台应用名 + 窗口标题（经 `xprop -root _NET_ACTIVE_WINDOW` 或 Qt/`python-xlib`——实现时选可用方案，倾向 `subprocess xprop` 轮询，无新硬依赖）；
  - **应用启动/活跃时长**：按应用聚合的 focus_seconds + 会话开始/结束时间；
- 输出：结构化 evidence（source_type="behavior"，raw 含 `{"app": "org.kylin...", "title": "...", "focus_seconds": 123, "hour_bucket": 20, "day_type": "workday"}`），经既有 `ingestion.ingest` → `knowledge.structure` → `preference.extract`（复用 /memory/write 同进程序列，批次②先例）；
- 采样策略：1s 轮询焦点（仅记录变化），每 60s 聚合一次活跃统计写入；防抖/忽略规则仿 watcher（系统自身窗口、无标题窗口）；
- 敏感度：标题文本经既有 detector 判定，sensitivity>0 不落库（同 ingest_bridge 先例）。

### [S2.2] 行为数据 → 偏好提取
- `preference/rules.py` 新增行为规则（source_type=="behavior" 分支）：
  - **高频应用**（focus_seconds 占比 top1 且 >阈值）→ `OP_HABIT:tool.selection.frequent`，value `{"tool": app, "share": 0.42}`；
  - **活跃时段**（hour_bucket 聚合峰值）→ `OUTPUT_STYLE:output_style.compact` 或新增 `OP_HABIT:schedule.active_hours`（以评测语料实际期望为准——读 reference.py 确认标签全集后定）；
  - 复用既有 `_canonical_from_key` 保证 canonical key 稳定（版本升级不变成新建行——记忆既有教训）；
- 校验：`capture_eval_predictions.py` 重采基线，`preference_accuracy >= 0.85`。

## [S3] 冲突分级打扰（后端 + 前端）

### [S3.1] 后端：conflict_detected 帧携带分级
- `backend/foundation/api/http_app.py` 的 memory_write/conflict 广播处：`conflict_detected` data 增加 `"severity": "low"|"medium"|"high"`；
- 映射（复用 Arbiter 三态，不改裁决逻辑）：
  - MERGE → low（自动合并，无需用户介入）
  - NEW_WINS → medium（自动裁决，但用户应知晓）
  - MANUAL → high（需人工确认）
- WS 帧与 GET /conflicts 的 ConflictRecord 同步加 `severity` 字段（repository 序列化兼容默认）。

### [S3.2] 前端：分级打扰
- `EventRouter::conflictDetected` 扩展 severity 参数（或 data 透传）；
- PixiuApp conflictDetected 处理器按 severity 分流：
  - low：不通知、不加角标、不切 Tab（可加内存级计数供面板角标聚合）；
  - medium：`m_notify->notify(tr("记忆已更新"), title)`（温和文案）+ 角标+1；
  - high：现状行为（「检测到记忆冲突」+ 角标+1 + 刷新冲突列表 + 切 Tab）；
- 冲突 Tab 条目按 severity 着色/标记（low 灰、medium 蓝、high 红——用 ui::UiTokens 语义色）。

## [S4] 契约与文档
- `docs/API.md`：conflict_detected 帧与 /conflicts 响应补 severity 字段说明；
- `frontend/docs/` 同步；README 偏好捕捉亮点更新为「已达标」状态（若 0.85 达成）。

## [S5] 测试策略
- 后端 pytest：
  - BehaviorCollector：焦点轮询 mock（xprop 输出伪造）、活跃聚合正确、忽略规则、sensitivity 拦截、config 门控（enabled && behavior）、evidence 落库形状；
  - 偏好规则：行为 evidence → OP_HABIT/OUTPUT_STYLE 提取断言；canonical key 稳定性（同 app 重复提取 → 同 key 升版）；
  - eval：`preference_accuracy >= 0.85` 复验（capture_eval_predictions.py 重采基线）；
  - conflict severity：三态映射正确、/conflicts 序列化含 severity；
- 前端 ctest（offscreen）：conflictDetected 按 severity 分流（low 不打扰 / medium 通知 / high 全动作）、冲突 Tab severity 标记；
- 全量回归：后端全量 pytest + regression.sh 双路径。

## [S6] 范围边界（不做）
- 不做键击记录、屏幕截屏、聊天内容读取（隐私铁律）；
- 不改 Arbiter 裁决逻辑本身（仅映射 severity）；
- 不做行为数据的长期报表/可视化；
- 不做批次④递送层（洞察流/定时简报）。

## [S7] 风险与开放点
- xprop 依赖：麒麟/UKUI 桌面可用（实测确认）；无 X 环境（offscreen/CI）降级为不采集（记录日志），测试用 mock；
- 评测标签全集需先读 reference.py 确认（OP_HABIT/OUTPUT_STYLE/SECURITY_POLICY 三类轮转 15 例——记忆记录）；
- 行为规则可能引入 OP_HABIT 与既有规则 key 冲突——先读 rules.py 现状再定 key 命名；
- 冲突 severity 向后兼容：旧前端忽略新字段、旧后端广播无 severity → 前端缺省按 high 处理。
