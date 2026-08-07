# 前端快速启动指南

> 模块 A · UKUI 桌面客户端

> **状态（2026-08-07）**：❌ 尚未开始，`frontend/` 仅含文档；本文为计划性说明。

---

## 环境要求

```bash
sudo apt install qtbase5-dev libqt5websockets5-dev qtbase5-dev-tools \
                 cmake g++ pkg-config

# 麒麟系统额外依赖
sudo apt install libkysdk-notification-dev libkysdk-shortcut-dev
```

## 构建运行

```bash
cd frontend

# 构建
cmake -B build -S .
cmake --build build

# 运行
./build/pixiu-frontend
```

## 开发降级（非麒麟系统）

```bash
cmake -B build -S . \
  -DPIXIU_HAVE_KYSDK=OFF \
  -DPIXIU_BACKEND_URL=http://127.0.0.1:8765

cmake --build build
```

降级模式下：
- `FloatingBall` → 普通 `QWidget`
- `ShortcutManager` → `QShortcut`
- `NotifyService` → `QSystemTrayIcon::showMessage`
