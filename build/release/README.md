# PIXIU 发布流水线脚手架（build/release）

> 目标：把**整个 PIXIU 软件**（UKUI 前端 + FastAPI 后端 + 本地 SQLite 记忆/同步
> 存储）打包成一个 `.deb`，让一台全新安装的麒麟 OS 机器能够 `dpkg -i` 直接安装
> 并运行；并提供可在开发过程中随时执行的本地 CICD 流水线，向 staging /
> production 发布 release 产物。
>
> 分支约定：本脚手架在 `main` 分支维护；后端（`feat/foundation`）与前端
> （`feature/frontend`）开发分支合并到 `main` 后，即可运行流水线出包。

## 目录结构

```text
build/release/
├── Makefile                  # 入口：make deb / test / publish-staging / publish-production
├── README.md                 # 本文档
├── scripts/
│   ├── functions.sh          # 公共函数（版本/架构/路径解析）
│   ├── build-deb.sh          # 主流水线：构建前端 + 打包后端 + 可选 wheels + dpkg
│   ├── test.sh               # 独立测试入口（前端 ctest + 可选后端 pytest）
│   ├── provision-target.sh   # 目标机预置：幂等安装 .deb 所需系统依赖（全新机器可用）
│   ├── vm-deploy-test.sh     # 麒麟测试 VM 部署+冒烟：上传/安装/服务/API/前端离屏
│   └── publish.sh            # 发布 staging/production（本地 dist + 可选 rsync 远端）
├── profiles/                 # 目标平台画像（发行版事实全部沉淀于此）
│   ├── kylin-v11-x86_64.env  # 麒麟 V11（openKylin）x86_64 —— 真机实测画像
│   └── generic-ubuntu.env    # 通用 Ubuntu（CI 默认）
└── debian/                   # .deb 元数据模板与维护脚本
    ├── control.in            # control 模板（@VERSION@/@ARCH@/@DEPENDS@ 由脚本替换）
    ├── postinst              # 安装后：建用户/数据目录/venv/装依赖/注册服务
    ├── prerm                 # 卸载前：停止并禁用服务
    ├── postrm                # 卸载后：purge 时清理数据
    ├── pixiu-backend.service # systemd：后端常驻服务（API 8765 + sync runtime）
    ├── pixiu.env             # 后端环境变量模板（安装到 /etc/pixiu/pixiu.env）
    └── usr/bin/
        ├── pixiu             # 一键启动器：确保后端服务在线后打开桌面客户端
        └── pixiu-backend     # 后端启动器：加载 /etc/pixiu 配置 + venv python
```

打包时还会将 `frontend/scripts/install-update` 安装到
`/usr/lib/pixiu/install-update`，作为 root-only 副本二次校验后调用 `dpkg`
的 `pkexec` 特权边界。

仓库根目录的 `.github/workflows/ci.yml` 在 `main`/PR 上执行后端全量测试、
前端编译测试和 `.deb` 打包；`.github/workflows/release.yml` 在 `v*` tag 上执行
同等验证、打入离线 wheels，并把 `.deb` 与 SHA-256 校验文件发布到 GitHub Release。
校验清单使用标准 `<sha256>  <asset-basename>` 格式，不写入构建机绝对路径。

流水线产物：

```text
build/release/out/           # 中间产物（stage 树 + .deb + sha256）——git 忽略
build/release/dist/<channel> # 发布目录（staging / production）——git 忽略
```

## 目标平台画像（profiles）—— 目标机事实的唯一真相源

所有在目标机实测发现的环境差异（apt 包名、Python 版本、wheels ABI、KYSDK
可用性、依赖缺失等）都必须沉淀在 `profiles/<platform>.env` 或流水线脚本里，
**禁止用一次性手工环境变量/手工装依赖来绕过**。当前内置画像：

| 画像 | 适用 | 关键事实 |
|------|------|----------|
| `kylin-v11-x86_64` | 麒麟 V11（openKylin）x86_64 | Python 3.12 无 pip/venv（postinst 自举）；Qt5 运行时包名 t64；apt 无 qtbase5-dev/kysdk-dev → KYSDK=OFF；wheels 按 cp312 |
| `generic-ubuntu` | Ubuntu CI/开发机 | python3-venv 可用；Qt5 非 t64 包名；wheels 按 cp312 |

新增平台时：拷贝一份画像并修改事实字段即可，流水线其余部分无需改动。
构建时用 `PIXIU_PROFILE` 选择画像（显式环境变量优先级高于画像）。

## 快速使用

```bash
# 一键：测试 + 构建 .deb（默认画像 kylin-v11-x86_64，KYSDK=OFF，离线 wheels）
PIXIU_PROFILE=kylin-v11-x86_64 make -C build/release deb

# 麒麟环境拿到 kysdk 开发包后构建原生版
PIXIU_PROFILE=kylin-v11-x86_64 PIXIU_KYSDK=ON make -C build/release deb

# 发布到 staging / production（生成本地 dist + 校验和；可选远端同步）
PIXIU_PUBLISH_URI=user@host:/srv/releases make -C build/release publish-production
```

## 全新麒麟机安装（生产流程）

```bash
# 方式一：脚本化（推荐，可重复）
make -C build/release build-deb                      # 产 .deb（含离线 wheels）
PIXIU_VM_HOST=192.168.122.197 bash build/release/scripts/vm-deploy-test.sh

# 方式二：手工两步（等价，供理解）
sudo bash build/release/scripts/provision-target.sh kylin-v11-x86_64   # 1) 系统依赖
sudo apt-get install -y ./build/release/out/pixiu_0.1.6-1_amd64.deb    # 2) 安装
```

`provision-target.sh` 与 deb 的 `postinst` 覆盖了麒麟 V11 的全部已知坑：
Python 无 pip/venv → get-pip.py 自举；PEP 668 externally-managed →
`--break-system-packages`；发行版自带包无 RECORD（如 typing_extensions）→
`--ignore-installed`；依赖优先从随包 wheels 离线安装；安装统一用
`apt-get install ./deb`（自动等待 dpkg 锁，规避 apt-daily 等后台任务占锁）。

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `PIXIU_VERSION` | `0.1.6` | 软件版本（写入 control Version） |
| `PIXIU_REVISION` | `1` | Debian 修订号 |
| `PIXIU_ARCH` | `dpkg --print-architecture` | 目标架构（amd64 / arm64） |
| `PIXIU_KYSDK` | `OFF` | 前端是否链接 KylinSDK（麒麟目标机用 `ON`） |
| `PIXIU_BUNDLE_WHEELS` | `1` | 打包时 `pip download` 后端依赖为离线 wheels |
| `PIXIU_PYTHON` | `python3` | 打包机 Python（wheels 按 `PIXIU_PYTHON_VERSION` 目标解析） |
| `PIXIU_PYTHON_VERSION` | `310` | wheels 目标 Python 版本（麒麟 V10 为 3.10） |
| `PIXIU_SKIP_TESTS` | `0` | `1` 时跳过流水线内测试 |
| `PIXIU_BACKEND_TESTS` | `0` | `1` 时额外执行后端 pytest（需已安装依赖） |
| `PIXIU_DEBIAN_DEPENDS` | 见 control.in | 覆盖 Depends 行（不同发行版包名不同） |
| `PIXIU_PUBLISH_URI` | 空 | 设置后 `publish.sh` 用 rsync 同步到远端 |

## 安装产物（全新麒麟机）

```bash
sudo apt-get install -y ./build/release/dist/production/pixiu_0.1.6-1_amd64.deb
# apt 自动解析并安装依赖（python3、Qt5 运行时等；kysdk 组件为建议项）
```

安装后：

- 后端以 `pixiu-backend.service` 常驻，监听 `127.0.0.1:8765`（HTTP + WS），
  SQLite 数据库自动创建于 `/var/lib/pixiu/pixiu.db`（首次启动自动迁移）；
- 桌面菜单出现 PIXIU 客户端；或在终端执行 `pixiu`（自动拉起后端后打开前端）；
- 配置在 `/etc/pixiu/pixiu.env`（API 端口、DB 路径、sync 开关等）；
- 安装脚本会生成每机唯一同步私钥口令，并将配置设为 `root:pixiu 0640`；
  从历史公开默认口令升级时会先重加密 Ed25519 私钥，设备 ID 与配对关系不变；
- P2P 同步网络默认关闭；需要时在 `/etc/pixiu/pixiu.env` 开启
  `PIXIU_SYNC_NETWORK_ENABLED=true` 并配置证书后重启服务。

## 当前已知边界（脚手架按现状落地，后续随开发自动受益）

- **引擎麒麟 SDK 绑定**：`backend/engine/kylin/cpp` 的 pybind11 扩展需在目标
  麒麟环境构建，本流水线暂以源码随包安装（`/usr/lib/pixiu/backend/engine/kylin`）；
  默认 `PIXIU_EMBEDDING=auto` 会优先调用真实 SDK，未构建绑定的 Debian 系机器
  自动使用可移植特征哈希向量器，`/memory/write` 与 `/memory/query` 保持可用；
  该路径语义质量低于麒麟模型，不计作正式召回率/时延验收。麒麟验收应设置
  `PIXIU_EMBEDDING=kylin`，让缺失绑定或 AI 运行时成为显式失败。
- **后端 Python 依赖**：优先随包携带离线 wheels（`PIXIU_BUNDLE_WHEELS=1`）；
  打包机无法下载时退化为安装时在线 `pip install`（需要目标机联网）。
- **WS 事件完整度**：`/events` 已完成真实入口注册并通过麒麟 VM 握手；当前仍需
  补齐 `conflict_detected` / `forget_confirmation` 两类业务广播。
- **OCR / 文本生成**：引擎侧待接入，不影响安装结构。

## 在测试机上克隆仓库（如需在目标机编译）

目标机使用 `github-personal` 作为 `github.com` 的 SSH 别名（配置于
`~/.ssh/config`，走 `ssh.github.com:443`）：

```bash
git clone git@github-personal:PlutoKeating/Project.PIXIU.git
```

不要使用 `git@github.com:...`（私有仓库会因密钥不匹配而失败）。

## 完整 CICD 建议流程

1. 开发分支合并到 `main`（本仓库既有流程：feature → staging → production）。
2. 本地/CI 执行 `make -C build/release deb`（自动跑前端 ctest，可选后端 pytest）。
3. `make -C build/release publish-staging` 产出 staging 包（供联调机安装验证）。
4. 验收通过后推送 `v*` tag，GitHub Actions 自动构建并发布 Release；也可以从
   Actions 页面手动运行 release workflow，只生成验证产物而不创建 Release。

GitHub Release 使用原生 amd64 与 arm64 托管 runner、`KYSDK=OFF`，分别产出
架构匹配的 `.deb`/`.sha256`。amd64 采用 `kylin-v11-x86_64` 运行依赖画像，
arm64 在麒麟画像完成真机取证前仅采用 `generic-ubuntu` 画像。因此 ARM 产物
只证明 Debian 通用降级画像可构建运行；麒麟 SDK 原生能力仍须在装有 SDK
开发包的麒麟自托管 runner 或真机（x86_64 / aarch64）分开验收。

## 实测记录（麒麟 V11 VM，2026-08-11 更新）

目标机：`192.168.122.197`（Kylin V11，x86_64，Python 3.12.3，Qt 5.15.19，
无 python3-pip/venv、无 kysdk 开发头文件）。

流水线：`make -C build/release build-deb`（profile=kylin-v11-x86_64，
KYSDK=OFF，35 个 cp312 wheels）→ `vm-deploy-test.sh`（force reinstall）。

| 验证项 | 结果 |
|--------|------|
| apt 预置 + `apt-get install ./deb` | ✅ 一次通过（venv 由 postinst 创建，依赖离线 wheels 安装） |
| `pixiu-backend.service` | ✅ active；uvicorn 监听 127.0.0.1:8765 |
| SQLite 数据库 | ✅ 首次请求自动创建 `/var/lib/pixiu/pixiu.db`（229KB，属主 pixiu） |
| `GET /conflicts` | ✅ 200 `{"conflicts":[]}` |
| `GET /sync/status`、`GET /sync/peers` | ✅ 200（真实状态；Ed25519 身份自动创建；口令配置修复后可用） |
| `POST /memory/write` | ⚠️ 当时为 500（旧版尚无 Debian embedding 降级；现已由 `auto` 模式修复） |
| 错误契约（400/404/422/500） | ✅ 统一 `{error, message, request_id}` + `X-Request-Id` 头 |
| 后端全量测试（VM 上跑最新源码） | ✅ 377 passed（foundation + engine） |
| 前端离屏冒烟 | ✅ 进程存活（timeout 正常退出 124） |
| 前端真实桌面 | ✅ 窗口映射确认（`wmctrl -l` 显示 PIXIU）；WS `/events` 403 为已知后端问题 |

本轮发现并已沉淀的修复：PEP 668 pip 自举、`--ignore-installed`（RECORD 缺失包）、
profile 优先级（默认值不得覆盖画像）、`PYTHONPATH=/usr/lib/pixiu`（顶层包 backend）、
uvicorn CLI 启动（避免双导入告警）、`apt-get install ./deb`（dpkg 锁等待）、
HTTP 级就绪等待（systemd active ≠ 端口就绪）、安装时生成唯一
`PIXIU_SYNC_KEY_PASSPHRASE`（后端同步私钥加密要求 ≥16 字符）、前端单实例守护（冒烟前先
`pkill -x pixiu-frontend`）。
