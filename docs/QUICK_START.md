# PIXIU 快速开始

## 直接安装

适用环境：银河麒麟桌面操作系统 V11 amd64。

先从 [v0.1.8 Release](https://github.com/PlutoKeating/Project.PIXIU/releases/tag/v0.1.8)
下载同版安装包和校验/签名资产，并按部署指南验证。仓库 submission 中旧包仅为历史归档。

```bash
# 在 Release 资产的下载目录运行
sha256sum -c pixiu_0.1.8-1_amd64.deb.sha256
sudo apt install ./pixiu_0.1.8-1_amd64.deb
pixiu
```

## 验证运行状态

```bash
systemctl --user status pixiu-backend.service
curl -s http://127.0.0.1:8765/version
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8765/capabilities
```

`/health` 应显示数据库就绪；银河麒麟严格画像的 `/capabilities` 应显示 Embedding 与 Vector Engine 使用 `kylin` runtime，并返回 `contest_ready=true`。

## 写入与检索

写入一条用户域记忆：

```bash
curl -X POST http://127.0.0.1:8765/memory/write \
  -H 'Content-Type: application/json' \
  -d '{"source_type":"MANUAL_CONFIG","raw":{"title":"报告使用简洁中文"},"scope":"user:demo"}'
```

检索记忆：

```bash
curl -X POST http://127.0.0.1:8765/memory/query \
  -H 'Content-Type: application/json' \
  -d '{"text":"我的报告偏好是什么","context_hint":{"top_k":5,"scope":"user:demo"}}'
```

## 使用 Agent

打开 KylinAgent 并新建会话。“麒灵系统云模型”默认选中，实际模型与授权由
“设置 → AI 模块管理”维护。PIXIU MemoryProvider 会在任务前召回相关记忆，并在
轮次结束后沉淀对话与工具结果。

需要使用自己的 DeepSeek、Anthropic 或 OpenAI 服务时，在 KylinAgent 的“云端模型
设置”中输入 API Key，点击“检测并保存”。风险工具会显示审批提示。

## 配对设备

在“同步与设备”中生成配对请求，另一台设备核对名称与六位 PIN 后确认。只有 `shared:*` 记忆参与同步，`user:*` 记忆保留在本机。

## 开发构建

```bash
git submodule update --init --recursive
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt -r backend/foundation/requirements-sync.txt
python -m backend.foundation.api.http_app
```

另开终端构建控制台：

```bash
cmake -S frontend -B build/frontend \
  -DPIXIU_HAVE_KYSDK=OFF \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build/frontend -j
PIXIU_BACKEND_URL=http://127.0.0.1:8765 ./build/frontend/pixiu-frontend
```

严格 V11 原生包：

```bash
sudo bash build/release/scripts/provision-target.sh \
  kylin-v11-native-x86_64 --with-build-deps
pip install -r backend/requirements-build.txt
bash build/release/scripts/prepare-native-supply-chain.sh
PIXIU_PROFILE=kylin-v11-native-x86_64 make -C build/release deb
```

严格构建使用洁净 checkout、V11 amd64 和 CPython 3.12；供应链准备需要 sudo
网络命名空间隔离权限。正式发布由 GitHub `pixiu-release` 标签工作流执行，
手动 `pixiu-kylin-v11-native` 只产生经过安装验证的候选 Artifact。

## 测试

```bash
python3 -m pytest -q backend integrations/kylin_agent/tests
ctest --test-dir build/frontend --output-on-failure
```

完整安装、升级、卸载与排障见 [部署指南](delivery/DEPLOYMENT_GUIDE.md)。
