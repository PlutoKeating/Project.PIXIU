# PIXIU 中文演示视频制作工程

当前制作版本：0.1.12，30镜，1920×1080、30fps，演示增强版时间轴499.333秒。文档、PPT和视频围绕“资料自动整理、可信设备共同记忆”展开。覆盖关系见 `../../docs/delivery/MATERIAL_ALIGNMENT.md`，视觉与声音依据见 `brief/制作依据.md`。

上一交付版：`renders/演示视频-0.1.12新版.mp4`；无配乐制作版：`renders/演示视频-0.1.12新版无配乐.mp4`。正式装配和摘要见 `review/current-final-package.json`，独立复核见 `review/independent-current-v5.md`。

## 首尾约定

片头与片尾使用同一套品牌画面、产品名、一句话介绍和slogan，均为257帧。片尾通过 `audio_reuse: "s01"` 复用原片头音频。`src/SceneOutro.tsx`、`src/brandCopy.ts` 和当前品牌素材沿用用户选定版本；介绍与slogan按原有口白时间展示。

## 当前素材

18个实拍场景、56项素材、10段原速裁片，来源和摘要记录在 `src/current-scenes.json`。目录与Dreaming包含整理进度、保存、查询、来源、对照、批准和再次查询；多设备包含共享设置、跨端查询、来源及三端更新观测。当前真实设置页补充模型选项与更新入口。

画面裁片按字幕时间选择，审批片段保留开始处的批准动作，查询片段突出结果；结束画面继续停留供阅读。实际源时段见 `review/current-playback-timing.json`。两段PPT实录采用相同原录，已在麒麟V11 LibreOffice 24.2完成放映验证。

## 配音与配乐

已交付版的30镜配音采用 Azure `zh-CN-YunfengNeural`。演示增强版新增口白统一使用原始语速（0%），首尾复用已指定原音；词级时间与镜头时长随本轮音频重新生成。原音和词级时间保存在 `raw/audio/`，文本、配置、音频摘要和字幕检查见 `review/current-narration-verified.json`。旁白保持170%线性增益。

配乐为用户选定的 ZENI - With You (Original Mix)，从15秒起取、音量15%，曲目接续交叉淡化4秒，结束淡出1秒。配置为 `src/bgm.json`，带配乐与无配乐版本使用同一视频流。运行混音脚本会同步工作台使用的配乐WAV。

## 制作与验证

环境：Node.js 24、`package-lock.json` 固定的 Remotion/React/TypeScript、FFmpeg/ffprobe、Python及 `requirements.txt`。这些是视频制作依赖。字体和许可位于 `public/fonts/`。

```bash
npm ci
python -m pip install -r requirements.txt
python scripts/narrate_azure.py --check-cache
python scripts/narrate_azure.py --region koreacentral
npm run prepare:timeline
npm run prepare:current
npm run prepare:directed
npm run check
npm run render:final -- .runtime/review-nobgm.mp4 --props='{"bgm":false}'
python scripts/mix_bgm.py --video .runtime/review-nobgm.mp4 --output .runtime/review-bgm.mp4 --report review/new-mix.json
```

语音服务通过本机 `SPEECH_KEY`、`SPEECH_REGION` 或交互式隐藏输入配置；也可使用 `--key-env` 与 `--region`。凭据仅用于合成进程。

`prepare_timeline.py` 校验整组原音后生成播放PCM、字幕和实际时长。`verify_narration.py` 检查文案、音色、来源摘要和镜尾；`verify_promo.py` 核对整片解码、30镜声音时间、图像与文字；`measure_audio_sync.py` 测量声音在输出文件中的位置。最后执行独立画面审查、整片语音回读和交付检查。

## 目录与交付

- `storyboard/`：当前镜头、文案及声音配置。
- `raw/`：真实原图、原录、配音和来源。
- `public/`：渲染素材；`src/`：当前画面和时间轴。
- `reference/`：模板、镜头卡、参考样片和审查依据。
- `review/`：可复核的帧、摘要、测量和审查报告。
- `renders/`：保存各次导出的成片；`.runtime/`：临时制作文件。

正式作品按 `../../docs/DELIVERY_PLAN.md` 第0节装配，演示视频ZIP内保存一份 `演示视频.mp4`，时长5—10分钟、ZIP大小200M以内。最终装配记录指定实际成片及摘要，源码、Word和PPT同步完成目录检查。所有制作变更在本地Git提交，大型媒体通过LFS保存。

## 演示增强版制作

新增口白以原始语速（0%）合成，首尾采用已指定的原音。字幕组件沿用现有字体、60px 字号、白色文字、7px 黑色描边、阴影与底部位置。`review/directed-voice-speed.json` 记录28段新口白的合成设置和首尾校验。

`capture_directed_desktop.py` 在 V11 演示环境以30fps录制真实鼠标与页面响应，按 `storyboard/directed-capture/` 保存操作计划和实际时刻。录制宿主使用现有 libvirt Python 绑定，演示系统使用 FFmpeg、xdotool 和 wl-clipboard；wl-clipboard 用于输入公开示例文字，输入后恢复剪贴板。`npm run prepare:directed` 生成剪辑素材与口白锚点；`DirectedProductScenes.tsx` 根据口白切换画面并安排阅读特写。

原录保存在 `raw/directed-0.1.12/`，播放裁片保存在 `public/directed/`。`reference/cursor-flyover.md`、准确示例源码与 Gallery 样片记录运镜参考。制作基准见 `brief/演示增强版设计.md`。

本轮画面按完整正文和控件范围取景，原图光标记录在 `native_pointer` 字段中。阶段、配对与遗忘分别展示实际确认动作，长期保存后展示检索结果；图书归还流程来自对应的实际来源页。临时配对值通过进程环境传入，采集时覆盖令牌区域；操作计划保存字段名称和发生时刻。

`verify_directed_constraints.py` 核对首尾素材、原音、原字幕组件、28段原速口白和全部画面锚点，并生成用于整片核验的源文件摘要。`transcribe_render.py` 对混合音轨进行语音回读，结果与最终成片通过音轨摘要对应。
