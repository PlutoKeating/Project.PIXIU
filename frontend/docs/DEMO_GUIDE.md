# PIXIU 前端演示说明（D-08 演示稿）

> 模块：Module A · UKUI 桌面客户端（`frontend/`）
> 分支：`feature/frontend`
> 适用对象：答辩/现场演示、目标机（x86/ARM 银河麒麟 UKUI）验收复现
> 配套清单：人工复测清单见 `UKUI_ADAPTATION_REPORT.md` 第 4 节；
> 后端问题交接见 `BACKEND_ISSUES.md`。

---

## 1. 演示前置条件

1. 已安装 `pixiu-frontend`（构建或安装 `.deb`，见 `QUICK_START.md`）：
   ```bash
   sudo apt install ./build/dist/pixiu-frontend_0.1.0-1_amd64.deb
   ```
2. 后端已启动（`/memory/write`、`/forget`、`/conflicts`、`/preference/*` 为
   真实实现；`/memory/query`、`/sync/*`、`/memory/flow/promote` 当前为占位）：
   ```bash
   python -m backend.foundation.api.http_app   # 默认 127.0.0.1:8765
   ```
3. 演示机为银河麒麟 UKUI 桌面会话（主题/通知/全局快捷键演示必需）。

## 2. 建议演示顺序（按场景串场）

### 2.1 录入记忆（走通 `/memory/write`）

1. 悬浮球贴边悬停，单击展开聊天框。
2. 输入问题或点击“📎”打开录入对话框（支持拖入本地图片预览；
   OCR 识别待后端接入后自动识别）。
3. 填写标题与内容，确认“录入记忆”。
4. 预期：收到“记忆已沉淀”通知（`memory_ready`，KYSDK 路径为系统通知）；
   聊天框出现写入确认气泡。

> 后端写入链路已真实实现；若后端未启动，界面呈现离线态，输入禁用。

### 2.2 遗忘（走通 `/forget` 两段式确认）

1. 输入以“忘记/遗忘/忘了”开头的指令（如“忘记那张 4 月的支出清单”）。
2. 预期：弹出确认对话框，展示目标与级联影响（证据/关系条数、不可撤销提示）。
3. Esc / 取消 → 不执行；确认遗忘 → 收到“已遗忘 N 条记忆”气泡。

### 2.3 冲突审计（走通 `/conflicts`）

1. 聊天框顶栏“记忆”打开记忆面板 → “冲突” Tab。
2. 预期：展示 old→new 字段对比与裁决结果；空列表显示友好空态。

### 2.4 偏好历史（走通 `/preference/{id}/history`）

1. 记忆面板 → “偏好” Tab，输入偏好 ID 后“加载历史”。
2. 预期：展示版本列表（v1/v2 值与时间）。

### 2.5 检索与同步（如实标注依赖，不虚构结果）

- `/memory/query` 当前返回 `not_implemented`，检索演示待 Module C 完成
  retrieval 后接通；期间可演示离线/失败提示行与“重试”按钮（输入保留）。
- 同步 Tab 为 Phase 6 占位页，设备配对/节点状态待 `foundation/sync` 落地。

### 2.6 桌面集成观感（真实 UKUI 会话人工验证）

- `Ctrl+Alt+P` 全局唤起（第二实例激活到主窗口）。
- 系统通知弹窗（记忆沉淀/冲突/同步事件）。
- 明暗主题切换实时跟随（本机已验证 dark→light→dark）。
- 窗口圆角阴影、悬浮球贴边、HiDPI/多屏定位。

## 3. 已知问题与限制（演示前必读）

| 项 | 状态 | 说明 |
|----|------|------|
| `/memory/query` 检索 | ⬜ 占位 | 查询演示阻塞，等待 Module C retrieval |
| `/sync/*` 设备同步 | ⬜ 占位 | Phase 6 阻塞，等待 `foundation/sync` |
| `/memory/flow/promote` | ⬜ 占位 | 流转 UI 阻塞 |
| WS `/events` 真实事件 | ⬜ 待 Module C | `/events` 未注册 + `ws.py` 导入缺失，见 `BACKEND_ISSUES.md` |
| 证据原文/详情 | ⬜ 契约缺失 | `source_evidence` 仅 ID，点击提示待后端提供 |
| 偏好列表 | ⬜ 契约缺失 | 当前为偏好 ID 输入入口 |
| 自定义图标 | ⬜ 轻量限制 | desktop 入口暂用系统主题图标 |
| 真实按键/通知/多屏 | ⬜ 人工 | 清单见 `UKUI_ADAPTATION_REPORT.md` 第 4 节 |

## 4. 演示口径建议

- 明确定位：PIXIU 是 UKUI 原生桌面入口，数据能力全部来自后端 API；
  前端展示离线/占位状态是设计行为，不是故障。
- 检索/同步链路未通前，演示聚焦：录入、遗忘两段式确认、冲突审计、
  主题跟随与全局唤起，均可在当前版本真实走通。
