# 模块 D · 测试与工具（Support/QA）

> **覆盖目录**：`backend/scripts/`, `backend/tests/`, 部分 `docs/`
> **开发人员**：1人（测试/运维/工具开发）
> **对其他模块**：零依赖，可使用 mock 数据独立工作

> [!CAUTION]
> mock/stub/portable 只用于开发回归。赛题最终报告必须在银河麒麟桌面操作系统
> V11 上真实调用指定 Embedding 与 Vector Engine，并覆盖完整 Agent 和多设备闭环。
> 团队已批准 ADR-0001；Module D 还必须验证 Module E 生命周期以及 A-11～A-14
> 上游版本、许可证、原创边界和实质性集成，不得只验证上游 Agent 能启动。

---

## 实现状态（2026-09-04）

- 行为采集 DI 接线测试使用真实 SQLite 服务，退出时必须调用 `stop_db()`，不能
  仅清空全局引用。新增子进程回归检查测试结束后能实际退出，覆盖 SQLite 工作线程
  泄漏；相关采集配置/API/行为组合 67 项在本地 Python 3.14 通过且进程正常退出。
  这不替代正式桌面采集与 Python 3.12/3.13 CI 验证。
- 🟡 **当前总览（2026-09-06）**：GitHub CI（`fd1a6d7`）在 Python 3.12/3.13
  各通过 823 项组合测试，前端 CTest 38/38；通用画像打包和三逻辑节点协议证据通过。
  V11 原生作业单独重建并验证，不能用通用测试代替真实 SDK 或三台物理设备。
- ✅ **现有发布/取证工具**：`build/release/scripts/` 提供版本与签名校验、用户级服务
  安装、升级/回滚、原生 SDK 探针、Agent 生命周期、三设备检查点、数据集冻结、
  逐样本性能与消融汇总、供应链记录与审计。Runtime 锁覆盖 58 个 wheel，
  bundled plugin YAML 与 DDGS 发现须在断网安装验证中通过。
- **材料整理**：`submission/` 只容纳按冻结要求生成的正式文件。编写源和截图在
  `docs/delivery/`，中间导出在 `build/release/out/`。`export-documentation.py` 生成
  项目报告和技术方案；`prepare-submission.py` 生成源码并校验目录、格式和摘要。
  最终三机、完整 Agent、性能消融和 GUI 安装升级结论继续按真实证据记录。

2026-09-09 视频制作：用户另行明确授权在 `submission/video-production/` 保存视频
工程及所有中间素材，位于正式两层同名目录之外。已有 30 镜中文草案、38 张既有原图、
Ink Press 模板参考与固定制作依赖；继续补采跨节点操作、配音字幕和成片终检。
视频工具依赖归该目录的 `package.json`／`requirements.txt`，不加入产品运行闭包。
目录校验器现仅排除这个明确授权的兄弟工作目录；正式目录内仍限制四项作品，其他
兄弟目录及工作目录符号链接仍拒绝。9 项目录回归通过，实际目录核对仅提示视频待补。

- 🟡 **历史测试基线（2026-08-11）**：foundation+engine 全量测试已由 A/C 模块补齐（麒麟 V11 真机
  pytest 377 passed）；`backend/.env.example` 已覆盖全部配置变量（含 `PIXIU_SYNC_*`，见
  `backend/foundation/docs/QUICK_START.md`）；前端回归脚本
  `frontend/scripts/regression.sh` 已固化。
- ✅ **打包发布脚手架**：`build/release/` 提供整包 .deb 构建、目标机预置
  （`provision-target.sh`）、目标系统本地安装验收与
  staging/production 发布；已在麒麟 V11 真机验证并发布 `v0.1.0-staging`。
- 🟡 **portable 回归已完成（2026-08-29），最终验收未完成**：自建测试数据集（`pixiu-family-expense-v1`：50 检索 +
  15 偏好 + 25 冲突）、性能压测（检索 P95 115ms ≤500ms）、验收评测报告
  `docs/acceptance/`（portable 管线达到数值阈值，非桩注入；不作为 H-01～H-03 证据）。
- ❌ **Docker 容器化**：产品采用原生 `.deb` 安装方式，不依赖 Docker，相关文件已移除。

---

## 开工要求（本地环境准备）

当前材料结构与检查结果见[材料检查记录](../../docs/delivery/PREPARATION_CHECK.md)。
文档导出使用 `build/release/requirements-docs.txt` 与 LibreOffice，DOC 必须独立打开并逐页检查。

开始开发前，**必须先补齐仓库内的官方麒麟 SDK submodule**：

```bash
git submodule update --init --recursive
```

- `third_party/kylin-coreai-embedding` —— 文本向量化 SDK（C API）
- `third_party/libkysdk-vector-engine-client` —— 向量数据库客户端（C++/gRPC）
- `third_party/kylin-agent`、`third_party/kylin-agent-runtime` —— 完整 Agent 与记忆接入的官方参考

测试、压测与容器化验证均依赖完整仓库（含 submodule），请勿跳过此步骤。

---

## 职责

| 领域 | 覆盖路径 | 说明 |
|------|----------|------|
| 评测框架 | `foundation/eval/` | Module C 子包，量化指标回归 |
| 工具脚本 | `backend/scripts/` | 建库、压测、部署脚本 |
| 测试数据集 | `backend/tests/datasets/` | 结构化测试数据 + 黄金查询集 |
| 单元/集成测试 | `backend/tests/` | 全模块 pytest 测试 |
| 环境变量模板 | `backend/.env.example` | 补全配置模板 |
| 文档补全 | `docs/*.md` | 辅助完善项目级文档 |

## 任务清单

### 1. 基础工具

原生 SDK 探针的记忆清理现使用 HTTP 0.5 预览凭证：限定 `user:acceptance`，核对
唯一探针标题和检索 ID，清理异常路径也先预览，遇到非探针目标即拒绝。检索同样
限定探针范围。此代码/夹具验证不能替代新版安装包的原生 SDK 真运行证据。

| 文件 | 说明 |
|------|------|
| `scripts/init_db.py` | 数据库初始化（建表 + 索引） |
| `scripts/capture_desktop.py` | 对现有 libvirt 桌面发送真实输入、采集 PNG；依赖宿主 virsh，区域截图需来宾 SSH/ImageMagick，X11 粘贴需 GTK 3 Python 绑定；不属于产品运行依赖 |
| `scripts/run.sh` | 一键启动脚本 |
| `scripts/eval.py` | 评测脚本（foundation/eval 已提供 CLI `python -m backend.foundation.eval`，可复用） |

> Module C 已交付 `foundation/scripts/phase7_pressure.py`（1000 次压测证据生成器，
> 产出 `foundation/evidence/` 报告），本岗位无需重复实现。

正式截图已整理 38 张 0.1.9 V11 实拍，覆盖主要单机操作并记录未完成场景，见
[截图素材索引](../../docs/delivery/assets/operations/截图素材索引.md)。图片数不代表全部验收通过；工具安全检查运行
`python3 -m unittest discover -s backend/scripts/tests -v`（7 项）。
全屏截图使用 libvirt 原始帧，区域截图只限定真实采集范围；不拼接、重绘或伪造结果。
原生 Wayland 的文本输入须检查实际字段，不能假定 X11 剪贴板已经跨协议同步。
采集工具测试不代表三设备、OCR、全部缩放或 GUI 升级矩阵完成。

### 2. 测试数据集

| 文件/目录 | 说明 |
|-----------|------|
| `tests/datasets/expense_50/` | 50 组家庭支出清单（附录 A 场景） |
| `tests/datasets/queries.json` | 语义查询黄金集（top-1 命中率校验） |
| `tests/datasets/preferences.json` | 偏好提取测试用例 |
| `tests/datasets/conflicts.json` | 冲突仲裁测试用例 |

### 3. 文档补全

- 配合其他开发者更新 `docs/` 下的项目级文档
- 编写效果/测试报告（汇入技术方案）
- 编写用户手册（汇入技术方案）

## 参考文档

| 内容 | 路径 |
|------|------|
| 验收规范 | `docs/AcceptanceTestSpecification.md` |
| 赛题原文 | `docs/OriginProblemDescription.md` |
| 开发计划 | `docs/DEVELOPMENT_PLAN.md` |
| 完整交付主实施计划 | `docs/IMPLEMENTATION_MASTER_PLAN.md` |

## 操作图片与文档导出

本次实拍已加入手册、部署指南、应用案例和项目报告。导出脚本解析各源稿的相对 PNG 路径，设置等比显示尺寸，并将图片摘要写入导出清单，避免临时 HTML 目录导致插图丢失。依赖仍为 `requirements-docs.txt` 和 LibreOffice，PNG 尺寸读取使用 Python 标准库。导出后需检查 PDF 图片和 Word 内嵌媒体，并逐页观察排版。
