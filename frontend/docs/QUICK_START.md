# 前端快速启动指南

> 模块 A · UKUI 桌面客户端

> **状态（2026-08-11）**：独立功能与 UI/UX polish 已完成，双路径 ctest 31/31
> 全绿；已随整包 .deb 在麒麟 V11 真机安装验证。本文为当前可用的构建/运行说明。
>
> 本指南仅验证 Module A 记忆控制台。团队批准的完整 Agent 宿主与 Module E 适配
> 尚需另行实现和验收，不能由前端进程启动或 ctest 结果代替。

---

## 环境要求

```bash
sudo apt install qtbase5-dev libqt5websockets5-dev qtbase5-dev-tools \
                 cmake g++ ninja-build

# 麒麟系统额外依赖（原生 kysdk 能力；缺失时用 KYSDK=OFF 降级构建）
sudo apt install libkysdk-notification-dev libkysdk-shortcut-dev libkysdk-qtwidgets-dev
```

## 构建与测试（KYSDK=OFF 降级路径，开发机可用）

```bash
cmake -S frontend -B build/frontend \
  -DPIXIU_HAVE_KYSDK=OFF -DCMAKE_BUILD_TYPE=Release -G Ninja
cmake --build build/frontend -j

# 全部 QtTest（31 项，offscreen）
QT_QPA_PLATFORM=offscreen ctest --test-dir build/frontend --output-on-failure
```

## 运行

```bash
# 方式一：接真实后端（默认 http://127.0.0.1:8765）
./build/frontend/pixiu-frontend

# 方式二：接演示桩（无后端/无麒麟 SDK，可完整演示 UI）
python3 frontend/scripts/demo_stub_server.py --port 8877 --badge 3
PIXIU_BACKEND_URL=http://127.0.0.1:8877 ./build/frontend/pixiu-frontend
```

环境变量：`PIXIU_BACKEND_URL`（后端地址，默认 `http://127.0.0.1:8765`）。
详细演示脚本与真实桌面验收清单见 `frontend/docs/DEMO_GUIDE.md` 与
`frontend/docs/UKUI_ADAPTATION_REPORT.md`。

## 打包进整包 .deb

前端由 `build/release/` 流水线构建并随整包安装（`/usr/bin/pixiu-frontend`、
桌面入口、图标；麒麟机器用 `PIXIU_KYSDK=ON` 获得原生快捷键/通知）。详见
`build/release/README.md`。

## 当前已知边界

- 后端 WS `/events` 已修复（2026-08-20），六类事件真实广播；前端事件路由
  已全部接线（见 `frontend/docs/BACKEND_ISSUES.md` 的闭环记录）。
- 引擎麒麟 SDK 绑定未构建/未运行时：写入/检索/OCR 按 `PIXIU_EMBEDDING` 降级
  （portable 特征哈希 / OCR_UNAVAILABLE），前端如实呈现错误与重试。
- 证据原文详情（`GET /evidence/{id}`）、偏好列表（`GET /preferences`）、
  QR 配对令牌（`POST /sync/token`）均已落地（2026-08-24）；剩余为真机人工
  复测项（全局快捷键真机按键、xprop 方言、麒麟 AI 运行时端到端）。
