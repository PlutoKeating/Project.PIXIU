# PIXIU 快速开始

## 直接安装

适用环境：银河麒麟桌面操作系统 V11 amd64。

```bash
cd submission/04-部署文档/01-可安装软件
sha256sum -c pixiu_0.1.7-2_amd64.deb.sha256
sudo apt install ./pixiu_0.1.7-2_amd64.deb
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
  -d '{"text":"我的报告偏好是什么","context_hint":{"top_k":5},"scope":"user:demo"}'
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
pip install -r backend/requirements.txt
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
PIXIU_PROFILE=kylin-v11-native-x86_64 make -C build/release deb
```

## 测试

```bash
python3 -m pytest -q backend integrations/kylin_agent/tests
ctest --test-dir build/frontend --output-on-failure
```

完整安装、升级、卸载与排障见 [部署指南](delivery/DEPLOYMENT_GUIDE.md)。
