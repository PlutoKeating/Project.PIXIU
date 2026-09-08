# PIXIU 中文演示视频制作工程

当前为制作中，不是最终视频。使用 video-shotcraft 的 Ink Press 模板，原版镜头源码保存在 `reference/ink-press/` 供逐镜核对；原版其他产品截图不复制、不入片。

赛方要求唯一引用 `../../docs/DELIVERY_PLAN.md` §0：5–10 分钟、演示所有已实现核心功能、ZIP 不超过 200M、作品内容匿名。现有两层同名交付目录保持原结构，完成后只向内层补入 `演示视频.zip`。

本目录按用户最新授权保存制作素材，是正式作品目录之外的工作目录。

`build/release/scripts/submission_layout.py` 只把该命名的兄弟目录排除在正式材料核对之外；正式同名目录内仍严格限制四项作品，其他额外兄弟目录仍拒绝。

- `brief/`：制作依据、颜色与功能覆盖要求。
- `storyboard/shots.json`：30 镜中文解说草案，预计 8 分 51 秒；须按实际配音长度和操作结果校准。
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

30 段解说原音已生成，当前稿净时长 444.024 秒；测量清单为
`review/narration-durations.json`，尚待逐段试听和最终字幕校准。

安装：本目录运行 `npm ci`（锁文件生成后）；Python 在独立虚拟环境安装 `pip install -r requirements.txt`。音频采用 [edge-tts](https://github.com/rany2/edge-tts) 的中文语音，逐句生成原音和时间信息，仅提交公开合成演示讲稿。完整时间线与渲染命令仍在制作中，不能把模板源文件当成产品视频。

当前已生成 `renders/开场审阅样片.mp4`：11 秒的中文配音与字幕开场，供制作检查，不能提交为比赛视频。运行 `npm run check` 做类型检查，`npm run still -- review/new-frame.png --frame=80` 出新静帧；完整重渲使用 `npx remotion render src/index.ts PixiuOpeningReview <新输出.mp4>`。默认不覆盖已有素材。`scripts/narrate.py --shots s01 s02` 生成所选讲稿的中文原音与逐词时间信息，按请求和音频摘要核对后复用；须在上述 Python 环境运行。

中文字体固定保存于 `public/fonts/`，来自系统 Noto CJK 字库的简体中文字体面，许可证随文件保存。当前无背景音乐，只有中文解说与模板转场音效。

依赖、缓存和临时运行数据库必须忽略；讲稿、采集脚本、原始素材、配音、字幕、审查关键帧及最终压缩包纳入 Git。大型二进制通过 LFS 保存。用户已授权本次制作提交后立即推送；不创建产品发布标签。
