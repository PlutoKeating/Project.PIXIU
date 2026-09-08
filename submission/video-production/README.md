# PIXIU 中文演示视频制作工程

当前为制作中，不是最终视频。使用 video-shotcraft 的 Ink Press 模板，原版镜头源码保存在 `reference/ink-press/` 供逐镜核对；原版其他产品截图不复制、不入片。

赛方要求唯一引用 `../../docs/DELIVERY_PLAN.md` §0：5–10 分钟、演示所有已实现核心功能、ZIP 不超过 200M、作品内容匿名。现有两层同名交付目录保持原结构，完成后只向内层补入 `演示视频.zip`。

本目录按用户最新授权保存制作素材，是正式作品目录之外的工作目录。

`build/release/scripts/submission_layout.py` 只把该命名的兄弟目录排除在正式材料核对之外；正式同名目录内仍严格限制四项作品，其他额外兄弟目录仍拒绝。

- `brief/`：制作依据、颜色与功能覆盖要求。
- `storyboard/shots.json`：30 镜中文解说草案，初始预计 8 分 51 秒；当前按配音校准为 554.100 秒。
- `raw/`：原始截图、录屏、配音与来源摘要；不改写原素材。
- `public/`：渲染使用的素材，裁切与取舍必须可追溯到原素材。
- `src/`、`scripts/`：视频时间线与制作工具。
- `reference/`：所选模板、镜头卡、声音许可与终检依据，仅供制作。
- `review/`：静帧、音视频检测和独立审查记录。

环境：Node.js 24、固定版本 Remotion/React/TypeScript（见 `package.json`），FFmpeg/ffprobe，Python 3 与 `requirements.txt`。采集额外复用仓库 `backend/scripts/capture_desktop.py`、libvirt、SSH 和目标机既有工具。视频依赖不加入产品运行依赖。

三端素材采集另使用 QEMU 的外部写时复制磁盘、OpenSSL 演示证书和 V11 仓库
`wl-clipboard` 2.2.1-ok1（原生 Wayland 中文输入）。这些是制作工具，不是产品新依赖。
`scripts/prepare_vms.py` 建立两个克隆；`configure_demo_guest.py` 在独立数据目录
启动已安装后端；`demo_api.py` 通过 SSH 访问本机公共 API，不保存配对令牌；
`verify_partition.py` 临时阻断第三端的同步 TCP 端口，结束时逐条移除自身规则；
`record_desktop.py` 保留实际像素与逐帧采集时间，默认每秒采样四帧，编码为三十帧。

2026-09-09：三端互发现、双向配对和首次共享查询已核实。环境为同一宿主上的三台
独立 V11 虚拟机，不是三台物理机验收。联机过程中修复了两处 Zeroconf 回调参数名，
当前是 0.1.9 安装版本加源码修复，正式交付前须重建安装包并同步源代码作品。
原用户数据库和配置未改写；演示服务占用正常后端端口，恢复时停止
`pixiu-video-backend` 并启动原 `pixiu-backend`。安装目录的 discovery.py 原件保存在
各虚拟机私有制作目录，磁盘链恢复说明在被忽略的 `.runtime/vms/RESTORE.txt`；
共享基盘仍被两个克隆依赖时，禁止合并原虚拟机写入层。证书私钥、数据库和配置
不作为媒体入库。

30 段解说原音已生成，当前稿净时长 456.408 秒；测量清单为
`review/narration-durations.json`，尚待逐段试听和最终字幕校准。

第二轮同步验证使用新的独立数据库（旧失败现场保留），已通过断连补齐、同 ID
并发收敛、遗忘重连传播及遗忘后检索为空。源文件摘要与原始 API 结果保存在
`raw/network/第二轮断连并发与遗忘传播.json`；修复提交为 `3531a75`，没有把开发
源码加载冒称为重建后的正式安装包。两台克隆的 Runtime 共享 scope 已设为
`shared:home`，修改前配置备份保留在各自私有制作目录；原虚拟机 Runtime 配置未改。

新增 `PixiuSharedChapterReview` 章节审阅合成：
`npx remotion render src/index.ts PixiuSharedChapterReview renders/集体记忆章节审阅.mp4`。
此镜沿用 Ink Press 的 PaperTitleCard/DigitRoll 实现，替换为蓝白主题和中文字体，
接入词级字幕草稿。输出 8.7 秒，只是章节引导片段。

安装：本目录运行 `npm ci`（锁文件生成后）；Python 在独立虚拟环境安装 `pip install -r requirements.txt`。音频采用 [edge-tts](https://github.com/rany2/edge-tts) 的中文语音，逐句生成原音和时间信息，仅提交公开合成演示讲稿。完整初剪使用 `npm run render:full -- <新输出.mp4>`，静帧使用 `npm run still:full -- <新输出.png> --frame=<帧号>`。不能把初剪当成最终视频。

当前已生成 `renders/开场审阅样片.mp4`：11 秒的中文配音与字幕开场，供制作检查，不能提交为比赛视频。运行 `npm run check` 做类型检查，`npm run still -- review/new-frame.png --frame=80` 出新静帧；完整重渲使用 `npx remotion render src/index.ts PixiuOpeningReview <新输出.mp4>`。默认不覆盖已有素材。`scripts/narrate.py --shots s01 s02` 生成所选讲稿的中文原音与逐词时间信息，按请求和音频摘要核对后复用；须在上述 Python 环境运行。

中文字体固定保存于 `public/fonts/`，来自系统 Noto CJK 字库的简体中文字体面，许可证随文件保存。当前无背景音乐，只有中文解说与模板转场音效。

依赖、缓存和临时运行数据库必须忽略；讲稿、采集脚本、原始素材、配音、字幕、审查关键帧及最终压缩包纳入 Git。大型二进制通过 LFS 保存。用户已授权本次制作提交后立即推送；不创建产品发布标签。

## 全片初剪（2026-09-09）

`renders/全片初剪-01.mp4` 已生成：1920×1080、30 帧、H.264/AAC，
容器时长 543.146667 秒，39129425 字节。`src/FullFilm.tsx` 接入全部 30 镜、
中文解说和字幕，真实截图经 `PageCam` 裁切展示；解释图明确标注为示意或接口观测。
当前仍有审阅标记，主要由截图和解释图构成，不能当作完整操作录像或最终交付。

`scripts/capture_memory_features.py` 通过公共 API 写入/检索四类知识、显式晋升
短期与中期记忆，另外只读查询演示数据库核对知识类型。成功证据为
`raw/network/结构化知识与记忆晋升-有效记录.json`；其他三份同前缀 JSON 是
脚本开发期间的未完成采集，见 `review/全片初剪-01.md`，不能依据文件名判定通过。
Agent 自动回合沉淀和跨端证据已保存，但客厅端随后的会话回答未通过，失败素材单独保留。模型回复声称调用记忆工具，但该条记录
来源是 CONVERSATION，不能据此认定显式工具调用成功。

下一版需接入实际操作视频、强化局部可读性、补齐 Ink Press 特征镜头及片尾，
逐段试听并核对字幕；重建安装包与正式源码保持一致后再做独立终检和正式打包。

第二版审阅稿为 `renders/全片初剪-02.mp4`（543.146667 秒、38334954 字节），
已接入两段真实检索录屏并调整遗忘页取景。整片解码与三处改动镜头抽帧通过；
具体视觉余项见 `review/全片初剪-01.md`，技术元数据绑定源码提交 `2ba42bf`。

片尾新增 `PixiuOutroReview`，可运行 `npm run render:outro -- <新输出.mp4>`。
真实页面切片组装、中文字标和三段式音效已适配，保留两版样片与实际抽帧。
`scripts/measure_audio_sync.py` 测量音轨滞后及音源峰值，依赖 NumPy；
`scripts/probe_prefetch_timing.py` 复用 Provider 测试夹具，依赖 pytest 与固定上游源码，
其默认退出 1 是已复现的首次预取为空，不是通过结果；`--ready-before-prefetch`
作为时序对照退出 0。详情见 `review/片尾与预取时序检查.md`。

第三版全片是 `renders/全片初剪-03.mp4`，9 分 3 秒、约 41 MB，已完成组装片尾、
声轨偏移补偿和整片解码。客厅 Agent 显式调用记忆工具成功复用了笔记本的家庭约定，
新取得的请求证据与操作素材已归档，随后第四版已将其接入核心共享章节；首次自动预取
为空和个别会话初始化过慢仍未修复。

共享章节新增 `PixiuSharedAgentReview`，通过 `npm run render:shared-agent -- <新输出.mp4>` 渲染。
s20 按实际配音在第 239 帧切入客厅完成后核对录屏，原速播放 300 帧后保留结果；
原始用户请求、工具完成卡和来源 ID 均取自真实画面，裁切及摘要见
`review/shared-agent-crops.json`。s21 明确切换到家庭节能约定的断连试验。
原始截图仅 1440×900，局部放大不等于高分辨率重采集；当前仍是审阅素材。

## 工作台拆分验证

`src/workbench.ts` 从同一 `timeline.json` 与 `FullFilm.tsx` 音效表生成画面、逐句字幕、
解说和音效轨道；画面单元关闭内置音轨与字幕，避免重复。标题和字幕的文案、
字号及颜色可编辑，字幕还可调整距底部位置；原有镜头运动参数保持在组件内。
工作台由 video-shotcraft 的 `workbench/scripts/open.mjs` 链接本工程后启动，
在其目录运行 `npm run parity -- --frames <绝对帧列表>` 检查导入前后的像素差异。
此检查另依赖 Python Pillow（已固定到制作依赖），不加入产品运行环境。
当前仍是初剪工作台，不能把可导入误称为最终交付；审阅结果保存在 `review/`。

工作台首轮校验在第 100、1400、10317、10537、10837、16400 帧的差异像素均为零，
原图与记录保存在 `review/workbench-parity-01/`；这是六帧抽样，不是整片或音轨全量一致性证明。
客厅演示克隆机已通过原生 `kscreen-doctor` 验证 3840×2160、scale=2，
重启演示客户端后取得清晰的新截图与工具卡展开录屏；新素材暂未入第四版。
具体模式、恢复命令及采样边界见 `review/4k-capture.json`。

当前最新全片为 `renders/全片初剪-04.mp4`：554.154667 秒、54735605 字节，
H.264/AAC、1920×1080、30 帧。整片解码通过，实际共享章节三阶段及下一镜
切换抽帧已核对。两段新解说起点相对字幕基准均约晚 0.27 帧；未主观试听。
元数据、视频摘要、原始渲染源码和抽帧见 `review/full-draft-04-*`。
这是第四版初剪，高清素材替换、功能及动效精修、独立终检、正式 ZIP 仍待完成。


## 高清与聚焦镜头（第五版初剪）

s03 接入 Gallery `spotlight-hero-card / spotlight-hero-card` 的准确示例，
保留推近、悬浮、归位和停留时序，替换为产品蓝白主题的共享记忆能力示意。
`raw/concept/` 保留可编辑 SVG；`npm run prepare:concept` 用固定 Noto 字体与
fontTools 转为 `public/concept/` 字形路径，避免截图纹理中文字缺失。
`npm run render:spotlight -- <新输出.mp4>` 生成 20 秒审阅片。

s20 已换为原生 3840×2160 素材；B/C 两台演示机在 scale=2 下重启客户端后采集。
录屏仍按实际采集间隔播放，编码 30 帧不代表采集达到了 30 帧。
高清请求和完成后核对片段的裁切记录为 `review/shared-agent-4k-crops.json`。

s07/s08 已使用同一条合成账单的录入、保存、新会话回答与证据详情。
实际 Runtime 日志确认 `pixiu_memory_search` 成功，三项金额合计 434.50 元，
知识及证据 ID 与公共 API 一致。`raw/network/高清账单实际工具检索.json`
只保存选定的工具事件与最终回答，不导出完整系统提示和模型请求。
`npm run render:bill -- <新输出.mp4>` 渲染 35 秒样片；`BillScene.tsx` 的
row-embed 来自准确参考示例，飞行体是截图裁片，片中明确标注逐行强调。
原始录屏都保留，但当前账单章节使用截图剪辑，不能称作连续实时操作录像。
书房约定的证据裁片作为中间素材保留，未接到该账单章节。

新增 public 顶层目录后，先重新运行工作台 `open.mjs <工程> --no-open`
更新静态素材链接，再执行 parity；否则新概念 SVG 会返回 404。
第五版 `renders/全片初剪-05.mp4` 已完成：554.154667秒、55101292字节，
整片解码及账单/跨端关键帧核对通过，音轨基准误差约0.27–0.29帧。
新版工作台五帧零差异，一帧字幕/审阅标记有5940像素差异，暂未通过；
独立终检和正式 ZIP 尚未完成，产品稳定性余项不变。
