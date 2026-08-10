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
2. 后端已启动（2026-08-10 `feat/foundation` 分支上 12 个 REST 端点已全部
   真实实现，含 `/memory/query`、`/sync/*`、`/memory/flow/promote`；
   真实检索依赖麒麟 embedding，需在麒麟环境运行；WS `/events` 仍待 Module C
   修复路由注册与导入问题，见 `BACKEND_ISSUES.md`）：
   ```bash
   python -m backend.foundation.api.http_app   # 默认 127.0.0.1:8765
   ```
3. 演示机为银河麒麟 UKUI 桌面会话（主题/通知/全局快捷键演示必需）。

## 2. 建议演示顺序（按场景串场）

### 2.1 录入记忆（走通 `/memory/write`）

1. 单击右下角悬浮球展开聊天框（左键按住可自由拖拽位置）。
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

### 2.4.5 偏好提取（走通 `/preference/extract`，2026-08-10 新增）

1. 先在聊天框录入一条记忆（记录其 evidence_id）。
2. 记忆面板 → “偏好” Tab → 点击“提取偏好”。
3. 预期：成功时显示“已提取 N 条偏好”；未录入过时提示先录入；后端契约
   错误按真实错误码展示（NOT_FOUND / INVALID_REQUEST 等）。

### 2.5 检索与同步（后端已实现，联调依赖真实环境）

- `/memory/query`：后端已实现混合检索（BM25+ANN+图），真实环境验证需麒麟
  embedding；开发机可用演示桩（见 §5）走通前端全流程。
- `/sync/*`：后端已实现配对/节点/状态/解绑；PIN 配对需在对话框填写另一台
  设备生成的配对令牌（base64）与 6 位 PIN——令牌生成端点在 Module C 侧尚未
  暴露给前端，当前可粘贴手工生成的令牌，或用演示桩完整走通 UI 流程。

## 5. 两种运行模式（2026-08-10 补充）

### 模式 A：演示桩（无后端、无麒麟 SDK，开发机可完整演示 UI）

```bash
# 终端 1：启动演示桩（默认 8765，可换端口）
python3 frontend/scripts/demo_stub_server.py --port 8877 --badge 3

# 终端 2：启动前端并指向演示桩
PIXIU_BACKEND_URL=http://127.0.0.1:8877 ./frontend/build/pixiu-frontend
```

演示桩按 docs/API.md 契约返回演示数据，并模拟 `/events`（memory_ready /
conflict_detected 推送），可完整查看录入/查询/遗忘/冲突/偏好历史/偏好提取/
配对/同步等全部界面与状态。

### 模式 B：真实后端（麒麟环境或已装依赖的开发机）

```bash
# 终端 1：启动真实后端（需已初始化麒麟 SDK submodule）
python -m backend.foundation.api.http_app        # 127.0.0.1:8765

# 终端 2：默认地址即 http://127.0.0.1:8765，直接启动
./frontend/build/pixiu-frontend
```

真实后端下，HTTP 端点全部真实生效；WS 事件推送待 Module C 修复 `/events`
后复测（前端已带指数退避重连与事件路由，修复后无需改前端）。

### 2.6 桌面集成观感（真实 UKUI 会话人工验证）

- `Ctrl+Alt+P` 全局唤起：第二实例激活通道已在本机真实会话验证（第二实例
  exit=1 → 主实例聊天框出现）；真实按键触发需在全新登录会话复测（当前
  会话未加载 grab，见 `UKUI_ADAPTATION_REPORT.md` 第 5 节）。
- 系统通知弹窗（记忆沉淀/冲突/同步事件）：`memory_ready` 弹窗已用测试
  专用 WS 桩（`scripts/ws_smoke_server.py`）在本机真实会话验证并截图留证；
  后端 `/events` 修复后以真实事件复测。
- 明暗主题切换实时跟随（本机已验证 dark→light→dark）。
- 窗口圆角阴影（截图留证，供人工确认视觉效果）、悬浮球拖拽/右下角定位、HiDPI/多屏定位。

## 3. 已知问题与限制（演示前必读）

| 项 | 状态 | 说明 |
|----|------|------|
| `/memory/query` 检索 | ✅ 后端已实现 | 真实检索需麒麟 embedding；开发机用演示桩走通 UI |
| `/sync/*` 设备同步 | ✅ 后端已实现 | PIN 配对需粘贴令牌；令牌生成端点未暴露，UI 流程用演示桩演示 |
| `/memory/flow/promote` | ✅ 后端已实现 | 前端已具备 transport 契约；ctx 上下文来源无端点，UI 暂不开放 |
| WS `/events` 真实事件 | ⬜ 待 Module C | `/events` 未注册 + `ws.py` 导入缺失，见 `BACKEND_ISSUES.md` |
| 证据原文/详情 | ⬜ 契约缺失 | `source_evidence` 仅 ID，点击提示待后端提供 |
| 偏好列表 | ⬜ 契约缺失 | 后端无列表端点；已补“偏好提取”入口（2026-08-10） |
| 自定义图标 | ⬜ 轻量限制 | desktop 入口暂用系统主题图标 |
| 真实按键触发 | ⬜ 人工 | 当前会话未加载 grab，需全新登录会话复测（见第 4/5 节） |
| 通知点击行为/多屏/x86/ARM | ⬜ 人工 | 通知弹窗已用 WS 桩截图留证；清单见 `UKUI_ADAPTATION_REPORT.md` 第 4 节 |

## 4. 演示口径建议

- 明确定位：PIXIU 是 UKUI 原生桌面入口，数据能力全部来自后端 API；
  前端展示离线/占位状态是设计行为，不是故障。
- 检索/同步链路未通前，演示聚焦：录入、遗忘两段式确认、冲突审计、
  主题跟随与全局唤起，均可在当前版本真实走通。
