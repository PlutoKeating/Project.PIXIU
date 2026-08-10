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

## 2026-08-10 Round 2（指针/焦点/顶栏稳定性与对话框细节）

第二轮 polish 已完成并本地验证，全部为纯视觉/交互细节，不涉及功能变更：

1. 指针/焦点态统一：按钮与 Tab 统一 `cursor: pointer`，按钮获得焦点时描边
   使用主题高亮色（`styles.qss`），键盘可达时焦点可见且与明暗主题一致。
2. 聊天框顶栏稳定：状态文案（在线/连接中/服务异常/离线）按最宽文案设置
   最小宽度，状态切换不再引起右侧按钮左右抖动；顶栏设置/记忆/关闭按钮
   补 tooltip 与 accessibleName（ARCHITECTURE §9 键盘可达）。
3. 危险对话框焦点语义：`ForgetDialog`/`RevokeDialog` 打开时默认聚焦“取消”，
   回车即取消，防误触不可逆操作（原有 Esc/关闭语义不变）。
4. 录入对话框提示文案修正：明确“粘贴文本内容；也可拖入图片作为附件预览…”，
   i18n 同步更新，不再提示尚未落地的 OCR 后续功能。

离屏渲染核对截图：`frontend/docs/screenshots/ui-polish-round2-2026-08-10/`
（聊天框 / 错误态 / 英文长文案错误态 / 思考骨架 / 悬浮球角标 / 遗忘·解绑·
配对·导入·设置对话框 / 记忆面板冲突·同步 Tab；offscreen 渲染，非真实桌面截图）。

剩余项不变：§4 旋转光环无处理中触发器暂不实现；§5 顶栏“在线 N 设备”与
§6 人工复测/后端契约阻塞项维持原记录。

## 2026-08-10 Round 3（长文案布局鲁棒性 + 指针/焦点细节收尾）

第三轮 polish 已完成并本地验证，全部为纯视觉/交互细节：

1. i18n 长文案不再被裁剪：系统提示（离线引导/写入回执等）与答案气泡同宽
   换行（`systemHint` wordWrap + 300px 上限），证据卡与气泡同宽、长证据 ID
   元信息在卡内换行——英文路径下不再出现列表视口硬裁剪或卡片比气泡更宽。
2. 指针光标一致性：移除 QSS 中无效的 `cursor: pointer` 规则（当前 Qt 版本
   不支持该 QSS 属性，启动即刷 “Unknown property cursor” 警告且不生效），
   改为在所有交互按钮上显式 `setCursor(Qt::PointingHandCursor)`（遗忘/解绑/
   设置/配对/录入对话框、记忆面板加载/刷新/重试/配对按钮），悬停反馈统一。
3. 键盘焦点可见性：扁平按钮（顶栏设置/记忆/关闭、附加、重试等）获得焦点时
   显示主题高亮描边，不再因 `border: none` 丢失焦点指示（ARCHITECTURE §9）。
4. 对话框尺寸鲁棒性：`SettingsDialog` 由固定 400×330 改为默认尺寸 + 最小尺寸，
   英文长提示需要时随内容增高（实测 en_US 下 sizeHint 282 高，仍保持 400×330）；
   `PairDialog` 设置 280px 最小宽度，PIN 输入/按钮不再局促。
5. 同步 Tab 长设备名行内省略（`peerNameLabel` 220px 内 ElideRight），在线状态
   不会被长名字挤出可视区。

离屏渲染核对截图：`frontend/docs/screenshots/ui-polish-round3-2026-08-10/`
（英文聊天消息流：用户气泡/长系统提示换行/长证据卡、设置对话框英文布局、
配对对话框、同步 Tab 长设备名省略；offscreen 渲染，非真实桌面截图）。

剩余项不变：§4 旋转光环暂不实现；§5 顶栏“在线 N 设备”与 §6 人工复测/后端
契约阻塞项维持原记录。本机实时 UKUI 会话复验：xcb 启动（主题/托盘/阴影/
英文 i18n/离线引导/健康探测）无回归；当前会话为 Wayland 合成器，wmctrl
不可枚举窗口，真实桌面截图仍按 offscreen 渲染记录。
