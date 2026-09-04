# PIXIU 发布流水线脚手架（build/release）

> 目标：把**整个 PIXIU 软件**（UKUI 前端 + FastAPI 后端 + 本地 SQLite 记忆/同步
> 存储）打包成一个 `.deb`，让一台全新安装的麒麟 OS 机器能够 `dpkg -i` 直接安装
> 并运行；并提供可在开发过程中随时执行的本地 CICD 流水线，向 staging /
> production 发布 release 产物。
>
> 分支约定：本脚手架在 `main` 分支维护；后端（`feat/foundation`）与前端
> （`feature/frontend`）开发分支合并到 `main` 后，即可运行流水线出包。

> [!CAUTION]
> 当前 `.deb` 已包含 PIXIU 原创 Module E，并由桌面用户启动器安装/升级到当前
> openKylin Agent profile；它仍不打包或冒充未修改的上游 Agent。真实宿主多轮闭环、
> `1751dd6` 已取得 V11 strict user-service 双 SDK compliant/`contest_ready=true` 证据；
> 完整 Agent、三设备、性能和最终安装矩阵尚未完成，因此不能据包结构宣称完整验收通过。

## 交付治理预检

在开始构建或整理赛事材料前执行：

```bash
make -C build/release governance
```

该命令依据 `docs/OFFICIAL_SOURCES.sha256` 校验两份禁止修改的赛事原件，并拒绝
包含未提交修改或未跟踪文件的工作区；CI 也执行同一检查。开发中仅需单独核验原件
时可运行 `build/release/scripts/verify-governance.sh --allow-dirty`，但该选项不得用于
候选发布审计。版本一致性继续由 `build-deb.sh` 在任何打包前强制检查。
治理测试的临时 Git fixture 采用有界重试清理，并始终保留实际测试退出码，避免后台
Git 维护造成的瞬时目录竞争把已通过门禁误报为失败；真实校验失败仍原样返回非零。

## 目录结构

```text
build/release/
├── Makefile                  # 入口：make deb / test / publish-staging / publish-production
├── README.md                 # 本文档
├── scripts/
│   ├── functions.sh          # 公共函数（版本/架构/路径解析）
│   ├── build-deb.sh          # 主流水线：构建前端 + 打包后端 + 可选 wheels + dpkg
│   ├── audit-agent-supply-chain.py # Agent 固定版本/敏感地址/发行证据门禁
│   ├── record-agent-supply-chain.py # 从真实构建/wheel 实物记录摘要并生成 SPDX/NOTICE
│   ├── three-device-evidence.py # 三台 V11 拓扑及并发更新检查点取证
│   ├── generate-release-manifest.py # 从源码/构建输入生成包内组件清单
│   ├── test.sh               # 独立测试入口（前端 ctest + 可选后端 pytest）
│   ├── provision-target.sh   # 目标机预置：幂等安装 .deb 所需系统依赖（全新机器可用）
│   └── publish.sh            # 发布 staging/production（本地 dist + 可选 rsync 远端）
├── profiles/                 # 目标平台画像（发行版事实全部沉淀于此）
│   ├── kylin-v11-x86_64.env  # 麒麟 V11（openKylin）x86_64 —— 真机实测画像
│   ├── kylin-v11-native-x86_64.env # 麒麟 V11 双 SDK 严格原生画像
│   └── generic-ubuntu.env    # 通用 Ubuntu（CI 默认）
└── debian/                   # .deb 元数据模板与维护脚本
    ├── control.in            # control 模板（@VERSION@/@ARCH@/@DEPENDS@ 由脚本替换）
    ├── postinst              # 安装后：准备 root-owned venv/依赖，停用旧系统服务
    ├── prerm                 # 卸载前：兼容停止旧系统服务
    ├── postrm                # 卸载后：不跨用户删除记忆数据
    ├── pixiu-backend.service # systemd user unit（API 8765 + sync runtime）
    ├── pixiu.env             # 用户默认模板（装到 /usr/share；首次桌面启动复制）
    └── usr/bin/
        ├── pixiu             # 一键启动器：后端 + 当前用户 Agent Provider + 控制台
        ├── pixiu-backend     # 后端启动器：加载 XDG 用户配置 + venv python
        ├── pixiu-user-setup  # 创建私有目录/口令并启动 user service
        └── pixiu-agent-integrate # Provider 幂等安装/激活；不覆盖非受管同名插件
```

从旧系统账户版升级时，首次桌面启动通过系统授权运行包内
`migrate-system-data`：先验证源 SQLite，再以 backup API 复制，复核 schema、全表计数
与同步身份摘要，并复制 Vector 数据和去路径化的用户配置。迁移有可恢复 journal，目标
非空时拒绝覆盖，成功后保留 `/var/lib/pixiu` 源数据，直至完整升级/回滚矩阵确认。

打包时还会将 `frontend/scripts/install-update` 安装到
`/usr/lib/pixiu/install-update`，作为 root-only 副本二次校验后调用 `dpkg`
的 `pkexec` 特权边界；`frontend/scripts/restart-client` 安装到同目录，以当前桌面
用户等待旧客户端退出后启动 `/usr/bin/pixiu`，不持有安装权限。
升级 GUI 会把当前用户实际 XDG 数据/配置/状态目录作为参数传入；特权 helper 只接受
`PKEXEC_UID`/`SUDO_UID` 对应用户 home 内、非符号链接且属主匹配的目录，并通过该用户
的 systemd manager 停启服务。数据库备份、配置恢复与健康失败回滚均作用于该用户域。
每个包还包含 `/usr/share/pixiu/release-manifest.json`：记录产品/Debian 版本、commit、
构建时间、架构、profile、KYSDK/Python ABI、HTTP API、Agent Memory API、schema、
Provider、两个 Agent 上游和双 SDK 的固定 commit/ref/许可证。实际运行时 SDK 版本仍
以目标系统包管理器和 `/capabilities` 取证为准，源码钉住版本不得冒充运行时版本。
生成器要求各 submodule 的 gitlink、实际 HEAD 一致且工作树洁净。`kylin-agent`
仓库的官方 Gitee API 元数据声明 `AGPL-3.0`；按 SPDX 3.0 对该已弃用标识的规范化，
清单记录为 `AGPL-3.0-only`，并保存元数据 URL、原值和规范化结果。许可证闭环不免除
完整对应源码、版权声明、NOTICE 与 AGPL 分发义务。

Agent 供应链另由机器门禁审计。普通开发可生成事实报告；正式候选必须使用强制模式：

```bash
python3 build/release/scripts/audit-agent-supply-chain.py \
  --root . \
  --evidence-dir build/release/evidence/agent-supply-chain \
  --output build/release/out/agent-supply-chain-report.json
python3 build/release/scripts/audit-agent-supply-chain.py \
  --root . \
  --evidence-dir build/release/evidence/agent-supply-chain \
  --require-ready
```

严格 KylinSDK 产品级冒烟脚本会在已安装 `/usr/lib/pixiu/venv/bin/python`
时自动切换到该隔离解释器，确保直接 SDK 调用与实际后端使用同一份锁定依赖：

```bash
python3 build/release/scripts/native-sdk-smoke.py \
  --base-url http://127.0.0.1:8765 \
  --deb build/release/out/pixiu_0.1.7-1_amd64.deb \
  --expected-commit "$(git rev-parse HEAD)" \
  --output build/release/out/native-sdk-smoke.json
```

目标环境取得真实实物后，按顺序记录。`--network-isolated` 是对该次构建/安装环境的
明确声明，并不代替日志；生成器还会拒绝日志/锁文件中的认证式 URL，自动读取每个
wheel 的 `METADATA`，不接受手填包名和版本：

```bash
python3 build/release/scripts/record-agent-supply-chain.py \
  --root . --evidence-dir EVIDENCE host-build --target-arch amd64 \
  --artifact HOST --source-archive SOURCE --build-log BUILD_LOG \
  --network-isolated
python3 build/release/scripts/record-agent-supply-chain.py \
  --root . --evidence-dir EVIDENCE runtime-wheelhouse --target-arch amd64 \
  --python-abi cp312 --wheelhouse WHEELS --lockfile LOCK \
  --offline-install-log INSTALL_LOG --network-isolated
python3 build/release/scripts/record-agent-supply-chain.py \
  --root . --evidence-dir EVIDENCE legal
```

`EVIDENCE`、`HOST` 等大写项是发布人员选择的候选归档路径/实物路径，不是可原样复制的
默认值。记录器复制实物进入证据目录，遇到同名但摘要不同的文件时拒绝覆盖；随后仍须
运行审计器，且认证式 URL 的上游源码阻塞必须独立解决。

策略文件固定两个上游 commit 和 Runtime 的三项真实版本声明。报告仅列出命中认证式
URL 的相对文件名，绝不回显匹配值；强制模式还要求 V11 宿主的目标架构产物、完整
对应源码归档、无网络构建记录与三者摘要，Runtime 的 Python ABI、全量 wheel、锁文件、
无网络离线安装日志与逐项摘要。SPDX 2.3 必须精确描述两个固定上游并覆盖 wheelhouse
全部包；NOTICE 必须包含组件名、来源、固定 commit 和许可证结论/未决标识，不能再用
任意非空文件占位。当前上游
宿主记录还必须精确匹配当前 release commit 和策略列出的全部下游适配输入摘要；任何
宿主构建脚本、补丁或兼容层变化都会让旧记录失效并阻断严格打包。
当前目标 V11 证据已满足这些条件并报告 `ready=true`；正式包必须再传入
`--expected-arch`，把宿主和 Runtime 证据精确绑定到候选包架构。未初始化 submodule
时，普通模式会把组件固定与 Runtime 版本事实记为不可用而不是崩溃；强制模式仍必然
失败。CPython 3.12/amd64 Runtime 及构建工具锁位于 `agent-runtime/`，是
`--require-hashes` 构建输入而非构建后输出；生成 wheelhouse 后必须反向生成并逐字节
比对运行时锁。固定上游 setuptools 当前不会自动把 bundled plugin 的 YAML 清单放入
wheel；构建器通过受版本控制的 `runtime-wheel-MANIFEST.in` 做发行层修正，不修改
submodule，并在全新离线 venv 中验证 DDGS 清单、插件发现和活动搜索 provider。
`postinst` 对该哈希锁闭包使用 `--force-reinstall`，保证同一 Runtime 版本上的 PIXIU
重装/升级也精确采用当前包内 wheel，而不是沿用旧文件集合。
报告同时固定输出 `agent-supply-chain-audit` 证据类型、仓库 commit 和明确 pass/fail，
供 D-07 原始证据归档做同版校验；`status=pass` 与 `ready=true` 必须同时成立。

## 完整 Agent 生命周期取证

先准备通过的 strict 原生 SDK 证据并启动同包 PIXIU、Kylin Agent 桌面宿主和固定
Runtime。受控场景不出现具体工具名；采集器会生成一次性随机标记和仅本用户可读的
临时文件，要求真实 Agent 自主完成系统命令读取和清理、联网搜索、记忆写入及现场审批。
清理对象只允许是本次采集器创建的临时标记文件；提示表达用户目标而不指定工具实现，
实际工具序列和审批次数由 SSE 事件判定：

```bash
python3 build/release/scripts/agent-lifecycle-evidence.py before-restart \
  --native-evidence NATIVE_SDK_JSON \
  --scenario build/release/agent-lifecycle-scenario.json \
  --state AGENT_CAPTURE_STATE_JSON
```

第一阶段成功后，完整退出并重新启动桌面宿主和 Runtime，再运行：

```bash
python3 build/release/scripts/agent-lifecycle-evidence.py after-restart \
  --scenario build/release/agent-lifecycle-scenario.json \
  --state AGENT_CAPTURE_STATE_JSON \
  --output agent-lifecycle.json
python3 build/release/scripts/agent-lifecycle-evidence.py validate \
  --output agent-lifecycle.json
```

大写路径是发布人员选择的实物路径，不是默认值。Gateway 只允许 loopback；若启用
Bearer 认证，只通过默认 `KYLIN_AGENT_API_KEY` 或 `--api-key-env` 指定的环境变量传入，
不得把密钥放到命令行或证据。审批必须在核对实际动作后手工输入与 run 绑定的确认语句，
不支持自动批准。中间 state 含继续运行所需的随机标记和会话标识，必须按敏感临时文件
保护且不得放入 D-07；最终 JSON 只保留哈希、计数、工具名和通过项。工具的通过只说明
采集程序契约已验证，最终状态仍取决于同一候选包在 V11 上的真实输出。

开发阶段可用 `build/release/testing/openai-compatible-mock.py` 启动确定性、无推理的
OpenAI-compatible 节点，再用 `run-agent-mock-acceptance.py --suite full` 经真实 Gateway
验证系统提示、多轮历史、SSE、审批、Shell、真实联网搜索及 PIXIU 记忆工具链；另以
`--suite memory --scope shared:<name>` 独立保存共享域记忆写入、检索、更新和同步状态
证据，避免重复联网请求的第三方限流影响共享记忆判定。两份结果共同覆盖工程链路，
不能互相替代。入口要求 `--expected-commit`，并核对已安装 release manifest 与后端
`/version` 后把候选身份写入 JSON。节点不保留原始提示、工具结果或密钥；输出固定带 `suite`、
`mock_only=true` 和 `not_release_evidence=true`。
它不能替代官方云端模型运行，也不得作为 D-07 七类正式主记录之一。

## 最终性能证据汇总

先在最终 V11 候选的桌面用户会话中，用已安装组件生成逐样本报告：

```bash
/usr/lib/pixiu/venv/bin/python \
  /usr/lib/pixiu/backend/scripts/capture_final_eval.py \
  --native-evidence NATIVE_SDK_JSON --output FULL_EVAL_REPORT_JSON
```

该入口强制 installed venv/组件路径、strict native 同版绑定、真实 Kylin Embedding 与
Vector Engine，以及隔离的评测状态；不得用 `sudo`、portable 报告或手填 execution
字段替代。原始逐样本报告和三变体对比完成后，用同一候选的五项输入生成性能主记录：

三变体不得手填汇总。固定任务集为
`build/release/agent-memory-ablation-tasks.json`（30 个互异的合成跨会话事实）。先在每个
参与端对已经启动的 Runtime 采配置快照；无记忆画像必须显式关闭内置 memory、用户
profile、外部 provider 和同步并只用非持久化 compressor context，单机画像必须启用 strict PIXIU provider 并关闭同步，
分布式画像必须绑定同一三设备 run 中两个不同节点的 manifest，且三节点全在线、队列
归零。配置变更后必须重启 Runtime，再采快照；采集时快照中的进程摘要必须仍与 Gateway
一致。

```bash
python3 build/release/scripts/agent-memory-ablation.py snapshot \
  --variant VARIANT --role teach-or-recall --native-evidence NATIVE_SDK_JSON \
  --runtime-config RUNTIME_CONFIG_YAML --runtime-env RUNTIME_ENV_FILE \
  --node-manifest DISTRIBUTED_NODE_MANIFEST_IF_REQUIRED \
  --output VARIANT_NODE_SNAPSHOT_JSON

python3 build/release/scripts/agent-memory-ablation.py capture \
  --variant VARIANT --native-evidence NATIVE_SDK_JSON \
  --task-set build/release/agent-memory-ablation-tasks.json \
  --teach-snapshot TEACH_NODE_SNAPSHOT_JSON \
  --recall-snapshot RECALL_NODE_SNAPSHOT_JSON \
  --teach-url TEACH_LOOPBACK_GATEWAY --recall-url RECALL_LOOPBACK_GATEWAY \
  --output VARIANT_REPORT_JSON

python3 build/release/scripts/agent-memory-ablation.py build \
  --variant-report NO_MEMORY_REPORT --variant-report SINGLE_DEVICE_REPORT \
  --variant-report DISTRIBUTED_REPORT \
  --dataset-manifest FINAL_DATASET_MANIFEST_JSON \
  --output MEMORY_ABLATION_JSON
```

每个任务由一个教学会话和一个全新召回会话组成；分布式组的教学与召回必须落在两个
不同的已证明节点。报告不保存提示词、模型正文、会话 ID 或明文业务载荷，只保存任务
ID、成功布尔值、轮数、工具名和运行摘要。工具会从 30 条逐任务结果复算成功率，三组
任务 ID、任务集摘要、release 与 dataset 必须完全一致；不要求结果单调，失败样本也
不得删除。`snapshot` 依赖 PyYAML，使用 PIXIU 已安装 venv 或具备项目依赖的解释器。

```bash
python3 build/release/scripts/final-performance-evidence.py build \
  --native-evidence NATIVE_SDK_JSON \
  --agent-evidence AGENT_LIFECYCLE_JSON \
  --dataset-manifest FINAL_DATASET_MANIFEST_JSON \
  --eval-report FULL_EVAL_REPORT_JSON \
  --comparison MEMORY_ABLATION_JSON \
  --output final-performance.json
python3 build/release/scripts/final-performance-evidence.py validate \
  --output final-performance.json
```

评测报告必须是上述入口产生的完整 `acceptance` profile，至少含 90 个逐样本结果；
汇总器先核对 installed 路径、双 runtime、native 摘要与 release identity，再重验 15 个
偏好、50 个检索、25 个冲突和 1000 个 P95 样本及四项官方阈值。消融 JSON 使用
`schema_version=1`、`status=pass`、release/dataset/task-set 摘要，并且 `variants`
恰好包含 `no_memory`、`single_device_memory`、`distributed_memory`；每组
`sample_count>=30`，`metrics` 恰好包含 0～1 的 `task_success_rate` 和正数
`mean_turns`。汇总不要求结果必须单调变好，但不得删掉不利数据。五个输入及逐样本
原始结果、固定任务集、配置快照和节点 manifest 仍须作为 D-07 去敏附件保存；汇总 JSON
不能替代它们。当前仅完成采集/复算工具及契约测试，最终 V11 三组运行尚未执行。

最终候选洁净且 strict 原生证据通过后，冻结 acceptance 数据集：

```bash
python3 build/release/scripts/final-dataset-manifest.py build \
  --native-evidence NATIVE_SDK_JSON \
  --dataset-output final-dataset.json \
  --manifest-output dataset-manifest.json
python3 build/release/scripts/final-dataset-manifest.py validate \
  --dataset-output final-dataset.json \
  --manifest-output dataset-manifest.json
```

生成器拒绝非当前 HEAD、脏工作树、非 strict 候选和官方赛题原文摘要漂移。输出固定
标注为附录 A 派生的团队合成语料，而非官方/第三方数据集；全部 90 例为冻结 test split，
无 train/validation 集。数据集 JSON 和 manifest 都进入 D-07，且不得覆盖已有输出。

D-07 归档不是对这些输出的简单打包：`build_evidence_archive.py` 会直接加载 native、
Agent、性能、数据集、安装/升级矩阵、三设备和 Agent 供应链的深度验证函数，并核对 Agent→native、performance→三主记录及
两个原始附件、dataset manifest→冻结 JSON 的摘要关系。冻结 JSON 会再次规范化并
检查 50/15/25 样本构成；逐样本报告与消融矩阵会重新评分且必须与性能摘要一致。
三设备最终套件还会递归重建两份拓扑、四份场景，并从归档内节点清单/检查点重新运行
原场景校验器；供应链会重读构建产物、对应源码、日志、wheel、锁文件、SBOM 与 NOTICE，
核对摘要、固定 commit、离线性和许可证覆盖。同样检查会在 ZIP 解包复验时重跑。

消融矩阵还会递归到固定任务集、三份逐任务报告、教学/召回配置快照和分布式节点
manifest；归档器重新运行变体校验、复算指标并确认跨节点身份。Runtime 原始配置和
`.env` 可能含密钥，禁止入档；只归档采集器产生的去敏快照及其原文件摘要。

## 安装、升级、回滚与卸载矩阵取证

`install-update-evidence.py` 不替操作者执行安装或卸载。每个真实动作之前和之后，使用
同一候选 `.deb` 采集状态；已安装快照必须能访问 loopback 后端，并要求服务、数据库和
strict contest capability 就绪：

```bash
python3 build/release/scripts/install-update-evidence.py snapshot \
  --package FINAL_DEB --expect-installed yes --output OPERATION-before.json
# 通过该场景规定的系统安装器、特权 helper 或 GUI 执行真实动作，并保存去敏日志/测试记录。
python3 build/release/scripts/install-update-evidence.py snapshot \
  --package FINAL_DEB --expect-installed yes --output OPERATION-after.json
python3 build/release/scripts/install-update-evidence.py operation \
  --kind OPERATION --before OPERATION-before.json --after OPERATION-after.json \
  --proof OPERATION-proof.log --exit-code 0 --outcome installed \
  --output OPERATION-operation.json
```

`OPERATION` 必须分别为 `fresh_install`、`reinstall`、`upgrade`、`rollback`、
`uninstall`、`gui_update`。首装的 before 和卸载的 after 使用
`--expect-installed no`；故障注入回滚必须记录 helper 的真实退出码 5 与
`--outcome recovered`；卸载使用 `--outcome removed`。GUI 记录必须来自真实
`UpgradeController → pkexec → /usr/lib/pixiu/install-update` 操作，不接受直接运行后端
API。每次动作使用独立的前后快照和 proof 文件，不得重复摘要或包含记忆正文、密钥、
个人路径。

六条 operation JSON 完成后生成主记录：

```bash
python3 build/release/scripts/install-update-evidence.py finalize \
  --native-evidence NATIVE_SDK_JSON \
  --operation fresh-install-operation.json \
  --operation reinstall-operation.json --operation upgrade-operation.json \
  --operation rollback-operation.json --operation uninstall-operation.json \
  --operation gui-update-operation.json --output install-update-matrix.json
python3 build/release/scripts/install-update-evidence.py validate \
  --input install-update-matrix.json
```

主记录、六条 operation、十二份快照和六份 proof 都必须作为 D-07 附件。归档器会按摘要
重新打开快照，核验状态转换和数据保留，再核对主记录引用的 strict 原生证据。当前工具
测试通过不等于最终真机矩阵通过。

## 三台设备拓扑取证

严格原生取证成功文件固定标识 `evidence_schema=1`、
`evidence_class=kylin-v11-native-sdk-product-lifecycle`、
`real_device_evidence=true` 与 `status=pass`。这些字段用于 D-07 汇总器做类型判断；
脚本未成功完成全部 SDK/产品生命周期时不会输出这组成功声明。

严格原生 SDK 取证通过且三台设备已完成双向配对、全部在线并等待同步队列归零后，
在每台设备本地使用同一个不含设备信息的 `run-id` 采集节点清单：

```bash
python3 build/release/scripts/three-device-evidence.py capture \
  --run-id run-YYYYMMDD-sequence \
  --native-evidence native-sdk-evidence.json \
  --output sync-node-evidence.json
```

采集器只允许访问 loopback 后端，并要求输入是通过状态的 V11 strict 原生证据；输出
不包含设备 ID、设备名、共享域原文、地址或记忆正文，只保存按本次 run 加盐的摘要、
版本/候选包摘要和同步计数。将三台设备的清单汇总到隔离目录后执行：

```bash
python3 build/release/scripts/three-device-evidence.py validate \
  --node node-a.json --node node-b.json --node node-c.json \
  --output three-device-topology.json
```

校验器要求三份清单来自同一 run、同一候选包/commit/版本/架构/Agent Runtime、同一
共享域，恰有三个不同身份，并且每台都看到相同三成员、全部 ONLINE、队列归零，采集
时间差不超过 300 秒。该报告只证明真实 V11 三节点全连接拓扑就绪，固定输出
`final_device_evidence=false`，并列出离线重连、并发冲突、墓碑防复活、私域不传播和
最终逻辑视图收敛五项待测场景；不得把它单独当作最终多设备验收结果。

### 并发更新场景取证

拓扑报告生成后，为本轮共享测试记忆准备仅含唯一检索标记的一行 UTF-8 查询文件。
先在三台设备均在线、队列归零时分别采集 `baseline/baseline`；随后暂停设备 A、B 的
同步，使用 `pixiu_memory_update` 从相同 `knowledge_id`/`version` 写入两个不同修订，
分别采集 `diverged/branch-a`、`diverged/branch-b`，未参与更新的设备 C 采集
`diverged/observer`。恢复 A、B 同步并等待三端队列归零后，三台设备分别采集
`converged/converged`。每次均在对应设备本地执行：

```bash
python3 build/release/scripts/three-device-evidence.py capture-concurrency \
  --topology three-device-topology.json \
  --node sync-node-evidence.json \
  --scope shared:team-demo \
  --checkpoint baseline --role baseline \
  --query-file scenario-query.txt \
  --output concurrency-baseline.json
```

九份检查点汇总后执行（每份使用一个 `--checkpoint`）：

```bash
python3 build/release/scripts/three-device-evidence.py validate-concurrency \
  --topology three-device-topology.json \
  --checkpoint node-a-baseline.json \
  --checkpoint node-b-baseline.json \
  --checkpoint node-c-baseline.json \
  --checkpoint node-a-diverged.json \
  --checkpoint node-b-diverged.json \
  --checkpoint node-c-diverged.json \
  --checkpoint node-a-converged.json \
  --checkpoint node-b-converged.json \
  --checkpoint node-c-converged.json \
  --output concurrent-update-scenario.json
```

工具要求九份文件绑定同一拓扑、候选包、三个节点清单、共享域和检索标记，并验证
共同基线、两条暂停同步的不同 v+1 分支、观察节点仍为基线，以及恢复后的三端相同
逻辑视图/版本与在线静默状态。输出只含加盐摘要、版本和同步计数，不含查询、正文、
域名或设备信息。单场景通过仍固定 `final_device_evidence=false`，并列出其余四项，
不得提升为完整三设备验收。

### 单节点离线写入与重连场景取证

先建立一条三端一致的 shared 基线并采集三份 `baseline/baseline`。随后隔离设备 A
并等待在线成员计数反映断连；在设备 B 更新该知识，等待 B、C 彼此传播完成且待发
队列归零。此时 A 以 `diverged/isolated` 采集，B、C 分别以
`diverged/writer`、`diverged/online-observer` 采集。恢复 A 并等待三端在线静默后，
再采集三份 `converged/converged`：

```bash
python3 build/release/scripts/three-device-evidence.py capture-offline \
  --topology three-device-topology.json \
  --node sync-node-evidence.json \
  --scope shared:team-demo \
  --checkpoint diverged --role isolated \
  --query-file scenario-query.txt \
  --output offline-node-a-diverged.json
```

将三阶段各三份、共九份检查点传给校验器：

```bash
python3 build/release/scripts/three-device-evidence.py validate-offline \
  --topology three-device-topology.json \
  --checkpoint node-a-baseline.json \
  --checkpoint node-b-baseline.json \
  --checkpoint node-c-baseline.json \
  --checkpoint node-a-diverged.json \
  --checkpoint node-b-diverged.json \
  --checkpoint node-c-diverged.json \
  --checkpoint node-a-converged.json \
  --checkpoint node-b-converged.json \
  --checkpoint node-c-converged.json \
  --output offline-write-reconnect-scenario.json
```

校验器要求隔离阶段 A 保持基线且在线成员不超过两个，B、C 在仅两个在线成员时仍
形成相同的 v+1 新视图；恢复后 A 必须精确追平，三端重新在线且队列归零。报告不含
查询、正文、共享域或设备信息。它为 N-02/N-03/N-05 建立证据契约，但没有真实三机
检查点输入、且其余场景未汇总前，仍固定为非最终证据。

### 私有作用域不传播场景取证

准备唯一查询标记，但使用 `user:*` 私有作用域。写入前在三端采集
`baseline/baseline`，确认均为零命中；仅在设备 A 写入私有记忆，再由 A 以
`post-write/writer`、B/C 以 `post-write/observer` 采集：

```bash
python3 build/release/scripts/three-device-evidence.py capture-privacy \
  --topology three-device-topology.json \
  --node sync-node-evidence.json \
  --scope user:team-demo \
  --checkpoint post-write --role writer \
  --query-file private-scenario-query.txt \
  --output privacy-node-a-post-write.json
```

把两阶段各三份检查点汇总校验：

```bash
python3 build/release/scripts/three-device-evidence.py validate-privacy \
  --topology three-device-topology.json \
  --checkpoint node-a-baseline.json \
  --checkpoint node-b-baseline.json \
  --checkpoint node-c-baseline.json \
  --checkpoint node-a-post-write.json \
  --checkpoint node-b-post-write.json \
  --checkpoint node-c-post-write.json \
  --output private-scope-scenario.json
```

通过条件是写入端恰有一条本地命中、两观察端继续零命中，所有待发队列为零，并且
每台设备前后的同步确认计数完全不变。输出仅保留条目数、计数和加盐摘要，不包含
查询、正文、私域原文或设备身份。该报告建立 N-06 的真实设备证据契约，但仍固定
`final_device_evidence=false`，直至真实三机输入和其余场景汇总完成。

### 墓碑传播与防复活场景取证

创建一条唯一 shared 记忆，把其 `knowledge_id` 单独写入 UTF-8 文件。三端先采集
`baseline/baseline`。隔离 A，在 B 完成两阶段遗忘并等待 B/C 队列归零后，A 采集
`deleted/isolated`，B、C 分别采集 `deleted/deleter` 与
`deleted/online-observer`。恢复 A 并等待三端收敛后采集 `reconnected/converged`；
再等待至少一个反熵周期并采集 `stable/stable`。每次在对应节点执行：

```bash
python3 build/release/scripts/three-device-evidence.py capture-tombstone \
  --topology three-device-topology.json \
  --node sync-node-evidence.json \
  --scope shared:team-demo \
  --checkpoint deleted --role isolated \
  --query-file tombstone-query.txt \
  --knowledge-id-file tombstone-knowledge-id.txt \
  --output tombstone-node-a-deleted.json
```

汇总四阶段各三份、共十二份检查点：

```bash
python3 build/release/scripts/three-device-evidence.py validate-tombstone \
  --topology three-device-topology.json \
  --checkpoint node-a-baseline.json --checkpoint node-b-baseline.json \
  --checkpoint node-c-baseline.json \
  --checkpoint node-a-deleted.json --checkpoint node-b-deleted.json \
  --checkpoint node-c-deleted.json \
  --checkpoint node-a-reconnected.json --checkpoint node-b-reconnected.json \
  --checkpoint node-c-reconnected.json \
  --checkpoint node-a-stable.json --checkpoint node-b-stable.json \
  --checkpoint node-c-stable.json \
  --output tombstone-no-resurrection-scenario.json
```

采集器同时查询 Agent 可见性和 `/sync/state/knowledge/{knowledge_id}` 的去载荷 CRDT
状态。校验要求：初始三端可见且为同一非墓碑状态；隔离期间 A 保持旧状态，B/C 不可见
且共享同一 clock+1 墓碑；重连和额外反熵后，三端仍是同一墓碑、均不可见且队列归零。
必须在墓碑 GC 保留窗口内完成四阶段采集；GC 后的“状态不存在”不会被接受为墓碑证据。
报告不含知识 ID、查询、正文、scope、操作 ID 或设备身份原文，并继续固定为非最终证据。

### 最终三设备证据门

四类场景全部完成后，重新在三台设备执行 `capture` 并用 `validate` 生成一份全新的
最终拓扑报告；不得复用初始三份节点清单。最后执行：

```bash
python3 build/release/scripts/three-device-evidence.py validate-final \
  --initial-topology three-device-topology-initial.json \
  --final-topology three-device-topology-final.json \
  --scenario concurrent-update-scenario.json \
  --scenario offline-write-reconnect-scenario.json \
  --scenario private-scope-scenario.json \
  --scenario tombstone-no-resurrection-scenario.json \
  --output three-device-final-suite.json
```

总门要求两份拓扑同 run、同候选包/commit/版本/架构、同三个身份及同一共享域，最终
拓扑使用三份全新节点清单；四个场景必须各出现一次、检查点数量正确、关键检查全部
通过，且报告生成时间位于初始与最终拓扑之间。只有该命令的输出允许
`final_device_evidence=true`；任一中间报告永远不能单独升级为最终证据。
发布脚本只从仓库根 `VERSION` 解析产品版本；环境变量只能作一致性断言，不能覆盖。
前端 CMake/独立 control 直接派生，Module E 源码只保留模板并在打包/激活时渲染；
产品版本已无静态构建元数据副本。版本与 Agent/manifest 成功路径测试也动态读取
根 `VERSION`；只有故意构造漂移或旧版兼容的夹具保留异版本值，正常升版无需同步
修改测试期望。组件清单测试同样从后端 `API_VERSION` 权威源读取 HTTP API，不复制
易漂移的期望值。`source_tree_clean` 会如实标记构建是否来自洁净工作树；CI 从完成的
`.deb` 反向提取该文件，并要求 commit、包版本、架构和画像一致。

仓库根目录的 `.github/workflows/ci.yml` 在 `main`/PR 上执行后端全量测试、
前端编译测试和 `.deb` 打包；`.github/workflows/release.yml` 在 `v*` tag 上执行
同等验证、打入离线 wheels，并把 `.deb`、SHA-256 与 Ed25519 签名发布到 GitHub Release。
每个架构同时发布 `pixiu_<version>-<revision>_<arch>.assets.json` 及其 `.sha256`、
`.sha256.sig`：JSON 枚举主 `.deb`、其 checksum 和独立签名的文件名、大小、SHA-256、
release commit 与 staging/production 通道；JSON 不收录自身摘要，因而无自引用，
生成前还会用固定公钥验证主包签名。JSON 的真实性由旁路 Ed25519 签名保证。
`publish.sh` 也生成同一六件套并要求离线签名密钥。
清单的 commit、Debian 版本和架构从 `.deb` 内组件清单及 control 交叉核对后取得，
不接受调用者覆盖；`generation.command` 保存仅含资产 basename 的规范化复现命令。
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
| `kylin-v11-x86_64` | 麒麟 V11（openKylin）x86_64 portable 对照 | Python 3.12；Qt5 运行时包名 t64；显式 `KYSDK=OFF` 以验证无专有 SDK 时的降级路径；wheels 按 cp312 |
| `kylin-v11-native-x86_64` | 麒麟 V11 x86_64 严格验收 | `KYSDK=ON`；画像安装 gsettings-qt、shortcut/notification/qtwidgets 与 Embedding/Vector 的官方开发包，任一原生扩展缺失即构建失败；双 AI SDK 为 Depends |
| `generic-ubuntu` | Ubuntu CI/开发机 | python3-venv 可用；Qt5 非 t64 包名；wheels 按 cp312 |

严格原生画像会把 `preinst` 渲染为 fail-closed 平台探测，在 PIXIU 文件解包前要求
Kylin V11 且包/系统架构一致。双 SDK 由 Debian `Depends` 解析并由后端严格启动预检
验证；Agent/runtime 因允许用户态安装，改在桌面用户激活 Provider 时检查，要求宿主
可执行且 runtime 版本命令成功、只报告一个 0.9.x 版本。严格启动器在该步失败时不会
继续打开控制台。generic 与 portable Kylin 画像保留非严格模式，其结果不得作为原生
验收。构建器同时强制 `KYSDK=ON` 与 `install_strict=1` 成对，禁止环境覆盖降级。

新增平台时：拷贝一份画像并修改事实字段即可，流水线其余部分无需改动。
构建时用 `PIXIU_PROFILE` 选择画像（显式环境变量优先级高于画像，但不得破坏
`KYSDK=ON`/`install_strict=1` 不变量）。

## 快速使用

```bash
# 一键：测试 + 构建 .deb（默认画像 kylin-v11-x86_64，KYSDK=OFF，离线 wheels）
sudo bash build/release/scripts/provision-target.sh \
  kylin-v11-x86_64 --with-build-deps
PIXIU_PROFILE=kylin-v11-x86_64 make -C build/release deb

# 麒麟 V11 严格原生版（先按画像安装公开构建依赖）
sudo bash build/release/scripts/provision-target.sh \
  kylin-v11-native-x86_64 --with-build-deps
PIXIU_PROFILE=kylin-v11-native-x86_64 make -C build/release deb

# 发布到 staging / production（生成本地 dist + 校验和；可选远端同步）
PIXIU_PUBLISH_URI=user@host:/srv/releases make -C build/release publish-production
```

## 全新麒麟机安装（生产流程）

```bash
# 在目标系统本地构建或取得匹配架构的正式资产后安装
sudo bash build/release/scripts/provision-target.sh kylin-v11-x86_64   # 1) 系统依赖
sudo apt-get install -y ./build/release/out/pixiu_0.1.7-1_amd64.deb    # 2) 安装
```

`provision-target.sh` 与 deb 的 `postinst` 覆盖了麒麟 V11 的全部已知坑：
Python 无 pip/venv → get-pip.py 自举；PEP 668 externally-managed →
`--break-system-packages`；发行版自带包无 RECORD（如 typing_extensions）→
`--ignore-installed`；依赖优先从随包 wheels 离线安装；安装统一用
`apt-get install ./deb`（自动等待 dpkg 锁，规避 apt-daily 等后台任务占锁）。

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `PIXIU_VERSION` | 根 `VERSION` | 可选版本断言；若设置则必须与权威版本文件一致 |
| `PIXIU_REVISION` | `1` | Debian 修订号 |
| `PIXIU_ARCH` | `dpkg --print-architecture` | 目标架构（amd64 / arm64） |
| `PIXIU_KYSDK` | `OFF` | `ON` 时同时强制前端链接 KylinSDK、构建后端双 SDK 原生扩展并打入包；缺依赖即失败 |
| `PIXIU_BUNDLE_WHEELS` | `1` | 打包时 `pip download` 后端依赖为离线 wheels |
| `PIXIU_PYTHON` | `python3` | 打包机 Python（wheels 按 `PIXIU_PYTHON_VERSION` 目标解析） |
| `PIXIU_PYTHON_VERSION` | `310` | wheels 目标 Python 版本（麒麟 V10 为 3.10） |
| `PIXIU_SKIP_TESTS` | `0` | `1` 时跳过流水线内测试 |
| `PIXIU_BACKEND_TESTS` | `0` | `1` 时额外执行后端 pytest（需已安装依赖） |
| `PIXIU_DEBIAN_DEPENDS` | 见 control.in | 覆盖 Depends 行（不同发行版包名不同） |
| `PIXIU_PUBLISH_URI` | 空 | 设置后 `publish.sh` 用 rsync 同步到远端 |

## 最终版本与一键升级门禁

当前应用内升级已具备 latest 查询、架构匹配、流式 SHA-256、强制签名资产、HTTPS/重定向白名单、
`pkexec` 授权、root-only 副本二次校验、包名/版本/架构检查和 `dpkg` 安装。安装后
helper 会核对实际 dpkg 版本，并轮询后端 `/version`、`/health`/schema 与包内
Provider 版本；全部通过才返回成功，健康失败使用专用退出状态。最终候选版还必须
补齐并验证。发布私钥只存在于 `PIXIU_RELEASE_SIGNING_KEY` 仓库 Secret；仓库固定公钥
DER SHA-256 标识为 `30c0f74a074c6f11a475000503bef1c2cb73794a8dcee9d283ea662e38ee28e8`。
本地签名须把私钥文件路径放入 `PIXIU_SIGNING_KEY_FILE` 后执行
`build/release/scripts/sign-release.sh <deb.sha256>`，不得提交私钥。最终仍须：

- 包内组件 manifest 已记录 Git/build/API/schema/provider/宿主/双 SDK 钉住版本和
  兼容范围，并由 CI 验包；仍须用一个发布输入派生 tag、CMake、Debian control 与
  Release 资产，并生成包含大小、摘要、签名和通道的包外最终资产 manifest；
- 双架构签名 CI 与 Kylin V11 有效/篡改签名已验证；
  `tests/test-release-key-rotation.sh` 用临时密钥和两个真实 `.deb` 验证“旧钥签发含
  新公钥的过渡版本、下一版切换新钥、旧钥拒绝下一版”，不接触或落盘生产私钥；
- `dpkg-repack` 旧包、SQLite/配置快照和健康失败自动回滚已通过提交 `ca35117` 的
  amd64/arm64 CI；Kylin V11 amd64 跨 revision 注入也以退出码 5 恢复旧版本、数据、
  配置和服务，最终候选仍须随完整安装矩阵重验；
- GUI 中显示版本、通道、发行说明、进度、授权和失败恢复；受控重启源码与包结构已
  实现/测试，最终候选仍须完成 V11 图形实证；
- 同版本重装、旧版升级、断网、坏签名、权限取消、安装失败与数据保留矩阵；
- strict `.deb` 已包含 Module E、最小适配后可重建的上游宿主与离线 Runtime；只读
  Provider 源位于 `/usr/lib/pixiu/integrations/kylin_agent/pixiu`。`pixiu` 启动时先
  拒绝不受管 user unit，再以事务方式更新 Agent profile 和包内 Gateway；Provider、
  `.env`、Runtime 配置或 Gateway 激活失败会恢复原快照。模型驱动完整生命周期仍须
  在配置真实推理提供商后取证，不能用无模型 Gateway 健康替代。

这些是团队发布门；逐项状态与赛事 D-01～D-10 文档台账见
`docs/DELIVERY_PLAN.md`。未完成前，现有 `0.1.7` 只能称为功能基线，不能称为最终
一键安装/升级交付。

## 安装产物（全新麒麟机）

```bash
sudo apt-get install -y ./build/release/dist/production/pixiu_0.1.7-1_amd64.deb
# apt 自动解析并安装依赖（python3、Qt5 运行时等；kysdk 组件为建议项）
```

安装后：

- 后端以当前桌面用户的 `pixiu-backend.service` 常驻，监听 `127.0.0.1:8765`
  （HTTP + WS），SQLite 数据库自动创建于 `$XDG_DATA_HOME/pixiu/pixiu.db`；
- 包版本写入 `/usr/share/pixiu/VERSION`，并由服务单元注入
  `PIXIU_PRODUCT_VERSION`；`GET /version`、`GET /health` 与 `GET /capabilities`
  分别用于组件版本、数据库就绪和赛题双 SDK 能力判定；
- 桌面菜单出现 PIXIU 客户端；或在终端执行 `pixiu`（自动拉起后端后打开前端）；
- 配置在 `$XDG_CONFIG_HOME/pixiu/pixiu.env`（API 端口、sync 开关等）；
- Vector Engine 的应用数据库由 `PIXIU_VECTOR_DB_PATH` 指定（默认
  `$XDG_DATA_HOME/pixiu/data/vector-engine.db`）；strict 启动会实际执行 `LoadDBFile`，失败
  即拒绝就绪，进程退出时执行 `Disconnect`；
- 包只在 `/usr/share/pixiu/pixiu.env.default` 携带公开默认模板；当前用户首次启动时
  创建 0600 配置并替换随机同步口令。运行配置不属于 dpkg conffile；
- P2P 同步网络当前默认开启（`PIXIU_SYNC_NETWORK_ENABLED=true`）；未完成可信配对/
  证书配置或不需要同步时，可在用户配置中显式关闭后重启 user service。

## 当前已知边界（脚手架按现状落地，后续随开发自动受益）

- **Agent 宿主与适配**：当前包已含 Module E 和幂等激活工具；Provider 已对经固定
  上游验证的 runtime 0.9.x、API/组件/产品版本及后端健康执行启动拒绝；安装器健康
  联动也已覆盖包内 Provider 版本。仍须完成 openKylin Agent 真实多轮/工具/生命周期
  验证，并补服务启动顺序和卸载边界；自动回滚当前切片虽已实证，最终候选仍须重验；
  不得直接把两个上游 submodule 当
  团队产物打包。

- **引擎麒麟 SDK 绑定**：通用 `KYSDK=OFF` 包只携带 Python 源码；严格
  `kylin-v11-native-x86_64` 画像会在构建中生成两个 pybind11 扩展并装入
  `/usr/lib/pixiu/backend/engine/kylin`，任一扩展缺失即中止打包；
  默认 `PIXIU_EMBEDDING=auto` 会优先调用真实 SDK，未构建绑定的 Debian 系机器
  自动使用可移植特征哈希向量器，`/memory/write` 与 `/memory/query` 保持可用；
  该路径语义质量低于麒麟模型，不计作正式召回率/时延验收。麒麟验收应设置
  `PIXIU_EMBEDDING=kylin`，让缺失绑定或 AI 运行时成为显式失败。
- **后端 Python 依赖**：优先随包携带离线 wheels（`PIXIU_BUNDLE_WHEELS=1`）；
  打包机无法下载时退化为安装时在线 `pip install`（需要目标机联网）。
- **WS 事件完整度**：`/events` 入口与六类业务事件均已完成；最终候选包仍须按
  同一 release commit 重跑真实前后端联调，不沿用历史 403 记录。
- **OCR / 文本生成**：OCR 已接入；离线文本生成仍待目标 SDK 环境，不影响安装结构。

## 完整 CICD 建议流程

1. 开发分支合并到 `main`（本仓库既有流程：feature → staging → production）。
2. 本地/CI 执行 `make -C build/release deb`（自动跑前端 ctest，可选后端 pytest）。
3. `make -C build/release publish-staging` 产出 staging 包（供联调机安装验证）。
4. 验收通过后推送 `v*` tag，GitHub Actions 自动构建并发布 Release；也可以从
   Actions 页面手动运行 release workflow，只生成验证产物而不创建 Release。

GitHub 通用 Release 使用 amd64 与 arm64 托管 runner、`generic-ubuntu`、
`KYSDK=OFF`，产物只证明 Debian 通用降级画像可构建安装，不宣称麒麟原生验收。
独立的 `pixiu-kylin-v11-native` 工作流仅在带 `kylin-v11` 标签的 x64 自托管 runner
手动执行：校验 V11、递归固定官方 submodule、按 strict profile 构建并安装，强制
`PIXIU_EMBEDDING=kylin`/`PIXIU_VECTOR_STORE=kylin`，激活用户态 Provider，再由取证
脚本绑定本次 `.deb`/checksum、包内与已装 manifest、PIXIU/双 SDK 包版本、Agent
runtime 及三个健康/能力端点；随后用唯一临时集合直接执行 SDK 的 create/load/upsert/
search/delete/drop，并验证产品 API 写入/召回/遗忘。Agent profile 使用临时隔离目录，
证据不包含主机、地址、路径或环境拓扑；generic 与 native 产物和报告始终分栏。

## V11 验收信息边界

仓库只保存脱敏后的候选版本测试报告和公开复现步骤，不记录任何本地测试设施的
地址、账号、连接方式、拓扑、SSH 配置或临时调试流程。
