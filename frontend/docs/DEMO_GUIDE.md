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
2. 后端已启动（24 个 REST 端点全部真实实现，含 `/memory/query`、`/sync/*`、
   `/monitor/*`、`/delivery/*`、`/memory/flow/promote`；六类 WS 事件
   （memory_ready / conflict_detected / forget_confirmation / sync_event /
   capture_event / pair_request）均已真实广播（`/events` 注册 2026-08-20 修复）；
   真实检索依赖麒麟 embedding，需在麒麟环境运行）：
   ```bash
   python -m backend.foundation.api.http_app   # 默认 127.0.0.1:8765
   ```
3. 演示机为银河麒麟 UKUI 桌面会话（主题/通知/全局快捷键演示必需）。

## 2. 建议演示顺序（按场景串场）

### 2.1 录入记忆（走通 `/memory/write`）

1. 单击右下角悬浮球展开聊天框（左键按住可自由拖拽位置）。
2. 输入问题或点击“📎”打开录入对话框（支持拖入本地图片预览；
   OCR 识别已接入（`POST /memory/ocr`，2026-08-24，无 SDK 环境返回
   OCR_UNAVAILABLE 并如实提示）。
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
- `/sync/*`：后端已实现配对/节点/状态/解绑；同步 Tab（2026-08-29）已接
  确认式配对主路径——`GET /sync/discover` 发现附近设备（含未配对）→ 对
  目标机发起 `POST /sync/pair/request`（6 位 PIN）→ 目标机弹「配对请求」
  确认/拒绝（`POST /sync/pair/confirm`）→ 确认后自动走既有 `/sync/pair`
  签名入网；QR/PIN 令牌流程保留为备选。

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

真实后端下，HTTP 端点全部真实生效；WS 事件推送已真实广播（`/events` 注册
2026-08-20 修复，六类事件均带广播路径）。

### 2.6 桌面集成观感（真实 UKUI 会话人工验证）

- `Ctrl+Alt+P` 全局唤起：第二实例激活通道已在本机真实会话验证（第二实例
  exit=1 → 主实例聊天框出现）；真实按键触发需在全新登录会话复测（当前
  会话未加载 grab，见 `UKUI_ADAPTATION_REPORT.md` 第 5 节）。
- 系统通知弹窗（记忆沉淀/冲突/同步事件）：`memory_ready` 弹窗已用测试
  专用 WS 桩（`scripts/ws_smoke_server.py`）在本机真实会话验证并截图留证；
  后端 `/events` 已修复（2026-08-20），以真实事件复测。
- 明暗主题切换实时跟随（本机已验证 dark→light→dark）。
- 窗口圆角阴影（截图留证，供人工确认视觉效果）、悬浮球拖拽/右下角定位、HiDPI/多屏定位。

## 3. 已知问题与限制（演示前必读）

| 项 | 状态 | 说明 |
|----|------|------|
| `/memory/query` 检索 | ✅ 后端已实现 | 真实检索需麒麟 embedding；开发机用演示桩走通 UI |
| `/sync/*` 设备同步 | ✅ 后端已实现 | 同步 Tab 已接确认式配对（发现→请求→目标机确认，2026-08-29）；QR/PIN 令牌流程保留为备选 |
| `/memory/flow/promote` | ✅ 后端已实现 | 前端已具备 transport 契约；ctx 上下文来源无端点，UI 暂不开放 |
| WS `/events` 真实事件 | ✅ 已实现（2026-08-20 修复注册） | 六类事件（memory_ready / conflict_detected / forget_confirmation / sync_event / capture_event / pair_request）均带广播路径 |
| 证据原文/详情 | ✅ 已实现（2026-08-24） | `GET /evidence/{id}` 返回证据详情，证据卡点击查看原文 |
| 偏好列表 | ✅ 已实现（2026-08-24） | `GET /preferences` 支持 scope 过滤；面板已接列表选择 |
| 自定义图标 | ⬜ 轻量限制 | desktop 入口暂用系统主题图标 |
| 真实按键触发 | ⬜ 人工 | 当前会话未加载 grab，需全新登录会话复测（见第 4/5 节） |
| 通知点击行为/多屏/x86/ARM | ⬜ 人工 | 通知弹窗已用 WS 桩截图留证；清单见 `UKUI_ADAPTATION_REPORT.md` 第 4 节 |

## 4. 演示口径建议

- 明确定位：PIXIU 是 UKUI 原生桌面入口，数据能力全部来自后端 API；
  前端展示离线/占位状态是设计行为，不是故障。
- 检索/同步链路未通前，演示聚焦：录入、遗忘两段式确认、冲突审计、
  主题跟随与全局唤起，均可在当前版本真实走通。

---

## 6. 批次②演示脚本：目录监视闭环（2026-08-26）

> 场景（附录 A）：「放清单图 → 自动入库 → 检索回查」。
> 演示的是「一次配置，永久监控」的目录源闭环：监控中心开启目录源并挂上
> 监视目录后，放入的文件经 watchdog 防抖 + 稳定性检查 → OCR/直读 → 入库，
> 期间 `capture_event` 实时推送、`GET /monitor/log` 可查、`/memory/query`
> 可回查。全程不需要重启 daemon，配置热生效。
> 契约见 `MONITOR_API_REQUIREMENTS.md` 与 `docs/API.md §3.17–3.19 / §4.5`。

### 6.1 准备（复用 §5 模式 B：真实后端）

```bash
# 终端 1：真实后端（批次② /monitor/* 端点与 monitor runtime 随应用启动）
python -m backend.foundation.api.http_app        # 127.0.0.1:8765

# 终端 2：前端（默认即 http://127.0.0.1:8765）
./frontend/build/pixiu-frontend
```

### 6.2 一键闭环脚本

```bash
#!/usr/bin/env bash
# 批次②目录监视闭环演示：放清单 → 自动入库 → 检索回查
# 用法：BASE=http://127.0.0.1:8765 MON_DIR=/tmp/pixiu-demo-monitor bash demo_batch2_monitor.sh
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8765}"
MON_DIR="${MON_DIR:-/tmp/pixiu-demo-monitor}"
IMG="${IMG:-${MON_DIR}/家庭支出清单.png}"
TXT="${TXT:-${MON_DIR}/家庭支出清单.txt}"
TIMEOUT="${TIMEOUT:-40}"

echo "==> [1/5] 准备监视目录：${MON_DIR}"
mkdir -p "${MON_DIR}"

echo "==> [2/5] PUT /monitor/config 开启目录源（热生效，无需重启 daemon）"
curl -sf -m 10 -X PUT "${BASE}/monitor/config" -H 'Content-Type: application/json' \
  -d "{\"enabled\":true,\"sources\":{\"directory\":true,\"clipboard\":false,\"behavior\":false,\"screenshot\":false},\"directories\":[\"${MON_DIR}\"]}" \
  | python3 -m json.tool

echo "==> [3/5] 放入清单文件（优先图片，图片入库走 OCR）"
if python3 -c 'import PIL' 2>/dev/null; then
  python3 - "${IMG}" <<'PY'
import sys
from PIL import Image, ImageDraw, ImageFont
out = sys.argv[1]
img = Image.new("RGB", (640, 360), "white")
d = ImageDraw.Draw(img)
font = None
for p in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
          "/usr/share/fonts/wps-office/HYXingKaiJ.ttf",
          "/usr/share/fonts/kylin-fonts-gb/国标楷体-GBT2312.ttf"):
    try:
        font = ImageFont.truetype(p, 32)
        break
    except OSError:
        continue
font = font or ImageFont.load_default()
d.text((40, 60), "家庭支出清单", font=font, fill="black")
for i, line in enumerate(["米 68 元", "食用油 45 元", "挂面 32 元"]):
    d.text((60, 140 + i * 60), line, font=font, fill="black")
img.save(out)
print("生成清单图片：", out)
PY
else
  printf '家庭支出清单\n米 68 元\n食用油 45 元\n挂面 32 元\n' > "${TXT}"
  echo "（无 PIL，直接用文本清单）"
fi

echo "==> [4/5] 等待捕获入库（轮询 GET /monitor/log，只认最近 3 分钟条目）"
fallback=""
start=$(date +%s)
while :; do
  read -r status summary <<< "$(curl -sf -m 5 "${BASE}/monitor/log?limit=30" | python3 -c '
import json, sys, time
now = int(time.time())
for e in json.load(sys.stdin)["events"]:
    if now - e.get("ts", 0) > 180:      # 只认最近 3 分钟，避免命中旧日志
        continue
    if e.get("source") != "directory":
        continue
    print(e.get("status", ""), e.get("summary", ""))
    break
')" || true
  if [ "${status}" = "ingested" ]; then
    echo "已入库：${summary}"
    break
  fi
  if [ -z "${fallback}" ] && { [ "${status}" = "ignored" ] \
      || [ $(( $(date +%s) - start )) -gt 10 ]; }; then
    # 图片未入库（ignored / 10s 无结果）＝本机无 OCR（麒麟 kysdk）：
    # 退回文本清单重试，文本直读不依赖 OCR。
    echo "（图片路径未入库——本机无 OCR？退回文本清单重试）"
    printf '家庭支出清单\n米 68 元\n食用油 45 元\n挂面 32 元\n' > "${TXT}"
    fallback=1
    start=$(date +%s)
  fi
  if [ $(( $(date +%s) - start )) -gt "${TIMEOUT}" ]; then
    echo "等待超时（${TIMEOUT}s）——检查后端日志与 watcher" >&2
    exit 1
  fi
  sleep 1
done

echo "==> [5/5] POST /memory/query 回查"
curl -sf -m 15 -X POST "${BASE}/memory/query" -H 'Content-Type: application/json' \
  -d '{"text":"我们买了米、食用油和挂面，一共花了多少钱？","context_hint":{"scope":"user:local","top_k":5}}' \
  | python3 -m json.tool \
  || echo "（查询超时/无答案：真实检索依赖麒麟 embedding，见 §2.5；入库闭环已由第 4 步验证）"

echo "==> 闭环演示完成"
```

> 已在开发机真实验证：PUT 配置热生效 → 放入 `家庭支出清单.txt` →
> `GET /monitor/log` 出现 `ingested`（「记住文件 家庭支出清单.txt」）。
> 图片路径在装有麒麟 kysdk OCR 的目标机上生效；无 OCR 的开发机会在
> 第 4 步自动退回文本清单。

### 6.3 前端可视化对照（与脚本并行演示）

1. 脚本 [2/5] 前后各截一张「设置 → 监控中心…」：Tab1 数据源矩阵应显示
   「目录文件监视」为开；Tab2 活动记录应实时追加 `state_changed` 与
   `ingested` 行（`capture_event` WS 推送，无需刷新）。
2. 脚本 [4/5] 入库后，在聊天框输入与查询语句相同的问句，预期返回含
   「家庭支出清单」的检索答案（真实检索依赖麒麟 embedding；开发机为
   BM25 通道结果，见 §2.5）。
3. 关闭后端再开监控中心：出现「离线，仅本地生效」提示行（离线回退，
   配置仍可编辑，恢复连接后对账）。

### 6.4 截图留证建议

- 会话为 X11 / XWayland 时用 `scrot`（UKUI 全屏会话可直接用 `PrintScreen`）：
  ```bash
  mkdir -p frontend/docs/screenshots/batch2-monitor-$(date +%F)
  scrot -d 5 frontend/docs/screenshots/batch2-monitor-$(date +%F)/step2-config.png
  scrot -u frontend/docs/screenshots/batch2-monitor-$(date +%F)/step4-log.png   # -u 截当前焦点窗口
  ```
- 建议留存 4 张：监控中心数据源页、活动记录页（含 ingested 行）、聊天框
  回查答案、离线提示行。
- 目标机为 Wayland 原生会话时，改用会话自带截图工具（UKUI 截图/快捷键）
  或先切回 X11/XWayland 会话再执行 `scrot`。
