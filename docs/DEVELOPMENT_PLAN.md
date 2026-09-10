# PIXIU 开发计划与分工

## 1. 当前版本

0.1.12 已发布。已完成的产品和测试结果见[发布记录](RELEASE_0_1_10_COMPLETION_PLAN.md)，目录迁移映射见[源码目录计划](SOURCE_MIGRATION_AND_PRODUCT_PLAN.md)。

首要平台为银河麒麟 V11 amd64，使用系统 Embedding 和 Vector Engine。Debian 兼容构建验证基础能力。正式包使用 Python 3.12，后端 CI 另测 Python 3.13。

## 2. 模块职责

| 模块 | 源码 | 职责 |
|---|---|---|
| A 桌面 | frontend/ | 工作区、消息、交互、宿主补丁 |
| B 记忆引擎 | backend/engine/ | 接入、知识、偏好、冲突、安全 |
| C 基础设施 | backend/foundation/ | API、解码、存储、检索、同步 |
| D 测试支持 | backend/scripts/、tests/acceptance/ | 场景验证、评测与记录 |
| E Agent | backend/agent/ | 记忆适配、文档工具、后台整理 |
| 平台 | backend/platform/ | 用户服务、启动、升级、迁移 |

## 3. 接口与依赖

- 前端和 Agent 通过 [API](API.md) 访问后端。
- Engine 通过 `backend/foundation/core/` 的模型和仓储接口访问存储。
- `backend/foundation/api/di.py` 负责服务装配。
- openKylin 宿主和 Runtime 固定在 `third_party/`；自有补丁归前端或 Agent 模块。
- `VERSION` 定义产品版本；依赖声明、锁和构建画像随源码维护。

## 4. 构建与验证

```bash
git submodule update --init --recursive
python3 -m pytest -q backend/engine/tests backend/foundation/tests backend/agent/tests
cmake -S frontend -B /tmp/pixiu-frontend -DPIXIU_MANAGEMENT_TESTS=ON
make -C build/release governance
```

通用构建使用 `KYSDK=OFF`，麒麟原生构建使用 `KYSDK=ON`。发布标签通过通用和原生检查后生成带签名的安装包。

## 5. 开发规范

### 5.1 文件归属铁律

| 模块 | 修改范围 |
|---|---|
| A | frontend/ |
| B | backend/engine/；公共接口调整位于 foundation/core/ |
| C | backend/foundation/ |
| D | 测试、工具与文档 |
| E | backend/agent/，通过公共 API 访问记忆服务 |

跨模块工作按用户批准的任务范围执行。上游源码使用已批准的补丁流程维护，决策见 `docs/decisions/`。

### 5.2 工作流程

1. 阅读根目录和相关模块文档，检查现有改动。
2. 修改当前任务涉及的代码及必要配置。
3. 运行对应验证，记录版本、环境和结果。
4. 同步依赖、构建与文档，检查 Git 差异并本地提交。
5. 根据用户授权执行推送和发布。

## 6. 交付

源码包含正式前后端、固定上游、许可证、依赖、构建脚本及测试。生成材料按 [DELIVERY_PLAN.md 第 0 节](DELIVERY_PLAN.md)执行。

本轮按用户要求收束开发与文档。后续验收集中维护于发布记录。
