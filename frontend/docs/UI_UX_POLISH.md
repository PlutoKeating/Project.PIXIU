# Module A · UI/UX Polish 统一待办

> 维护者：Module A
> 策略：功能完整、逻辑正确、测试可靠为第一优先级（2026-08-09 起）。本清单只收集
> **纯视觉/体验**问题（颜色、间距、字体、圆角、阴影、动画、布局一致性），
> 不在功能开发阶段逐项打磨；待 `DEVELOPMENT_PLAN.md` 中所有 Module A 可独立
> 实现的功能完成或被明确阻塞后，进入集中 Polish 阶段统一处理。
>
> 规则：明显影响可用性/可访问性的问题直接修复，不进入本清单；视觉细节问题
> 一律登记到此处。
>
> 2026-08-09 更新：Module A 可独立实现的功能已全部完成或明确阻塞（见
> `DEVELOPMENT_PLAN.md` §1.2/§8），自本日起进入统一 UI/UX polish 阶段，
> 按下表逐项处理；处理时仍保持“可用性/可访问性优先”原则。

> 2026-08-09 Polish 基线更新：统一视觉/交互基础规范已落地并应用到全部
> 页面（见下方 ✅ 标记），完整回归 OFF/ON 双路径通过；剩余项均为人工
> 复测或后端契约阻塞（§6）。

---

## 1. 状态/语义颜色仍为内联硬编码

已统一迁移。语义色收敛到 `src/app/UiTokens.h`（success/warning/error/muted/
badge + 明暗变体），控件不再出现内联色值；危险按钮统一走
`ui::dangerButtonStyle()`：

- ✅ `ChatWindow::setBackendState`：`ui::textStyle(Success/Warning/Error/Muted)`
- ✅ `MemoryPanel::setSyncStatus` / 同步 Tab 节点状态 / 元信息：语义角色
- ✅ `MessageList::appendQueryError`：错误角色
- ✅ `ImportDialog` 拖入占位框：`styles.qss` 中 `palette(mid)` 虚线边框
- ✅ `ForgetDialog`/`RevokeDialog` 确认按钮：统一 `ui::dangerButtonStyle()`
  （明暗自适应 + hover/pressed）
- ✅ `PairDialog::setResultFeedback`：成功/失败语义角色

## 2. 字号/间距未完全统一

- ✅ 字号分级统一为设计令牌：`ui::Font`（标题 14pt / 正文 11pt / 辅助 9pt），
  QSS 侧经 objectName 规则统一控制，不再散落 `font-size: …px` /
  `setPixelSize`（悬浮球自绘徽标数字除外）。
- ✅ 气泡内边距按 §7.2/7.3 统一为 12px；证据卡 10px；同步 Tab 节点行间距
  按 4/8 栅格；输入栏 8px 间距。
- ✅ `styles.qss`：`QListWidget#messageList` 透明背景保留，列表/滚动条、
  按钮/输入框/Tab/菜单均已定制控件状态样式（hover/pressed/disabled/focus）。

## 3. 图标与悬浮球视觉

- ✅ 悬浮球中央替换为 PIXIU 三节点网络标记（白色，明暗主题均清晰，
  随设备像素比绘制，HiDPI 清晰）。
- ✅ 角标样式复核：语义红色 + 弹入/呼吸动效 + 99+ 截断。
- ✅ 聊天框顶栏设置入口改为运行时绘制齿轮图标（`src/app/UiIcons.h`），
  颜色跟随 Palette 并在主题切换时重建；托盘/desktop 继续使用内嵌
  `pixiu.svg`。
- 附注：输入栏“📎”与关闭“✕”沿用系统字形，符合 UKUI 轻量风格，暂不替换。

## 4. 动效未完全落地

- ✅ 已实现：聊天框淡入淡出（150ms）、悬浮球角标弹入 + 呼吸
  （`FloatingBall::startBadgePulse`）、答案加载骨架屏
  （`ThinkingSkeleton`，三条圆角条 + 呼吸脉冲）。
- ⬜ 处理中“旋转光环”：当前产品路径无处理中状态触发器，暂不实现
  （避免无意义动画）。

## 5. 布局与窗口细节

- ✅ 聊天框无边框边缘/角落拉伸（最小 360×440），默认 420×560；记忆面板
  默认 560×480、最小 480×400，可经原生窗口边框调整。
- 无边框窗口阴影仅 KYSDK 路径生效（`UkuiWindow`）；OFF 开发路径视觉差异
  记录在案，不作为缺陷。
- 聊天框顶栏“同步状态”当前仅显示后端连接状态（在线/离线），设计稿的
  “在线 N 设备”等待 `/sync/*` 真实契约落地后接入（保持阻塞记录）。

## 6. 主题/多端人工复测项（不属于自动修复）

- HiDPI 与多屏下悬浮球/聊天框/面板位置与缩放（x86/ARM 目标机）。
- 深浅主题下同步 Tab 节点行、证据卡、对话框明暗对比。
- 全局快捷键真实按键触发（全新登录会话复测，见 `UKUI_ADAPTATION_REPORT.md`）。
- 二维码配对页视觉（令牌契约落地后设计）。
- 本轮 Polish 的离屏渲染核对截图：
  `frontend/docs/screenshots/ui-polish-2026-08-09/`
  （悬浮球角标 / 聊天框问答+证据 / 骨架屏 / 同步 Tab / 对话框 /
  英文长文案错误态；offscreen 渲染，非真实桌面截图）。

---

## 记录来源

- 2026-08-09 真实 UI 验收截图：`frontend/docs/screenshots/ui-acceptance-2026-08-09/`
  （悬浮球 / 聊天框 / 问答+证据 / 录入对话框）。
- 本轮功能开发（同步管理 UI、WS 事件路由）过程中发现并登记，功能已按
  “可用、可访问、布局基本正确”标准实现，未逐项打磨。
- Polish 阶段提交记录：设计令牌（`d82b9c0`）、主题感知图标（`6047157`）、
  动效（`d85f6a3`）、窗口/面板尺寸（`4b184f3`）。
