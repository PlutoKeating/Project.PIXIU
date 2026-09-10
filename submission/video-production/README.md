# PIXIU 中文演示视频制作工程

当前制作版本：0.1.12，30镜，1920×1080、30fps，实际时间轴437.667秒。文档、PPT和视频围绕“资料自动整理、可信设备共同记忆”展开。覆盖关系见 `../../docs/delivery/MATERIAL_ALIGNMENT.md`，视觉与声音依据见 `brief/制作依据.md`。

当前成片：`renders/演示视频-0.1.12新版.mp4`；无配乐制作版：`renders/演示视频-0.1.12新版无配乐.mp4`。正式装配和摘要见 `review/current-final-package.json`，独立复核见 `review/independent-current-v5.md`。

## 首尾约定

片头与片尾使用同一套品牌画面、产品名、一句话介绍和slogan，均为257帧。片尾通过 `audio_reuse: "s01"` 复用原片头音频。`src/SceneOutro.tsx`、`src/brandCopy.ts` 和当前品牌素材沿用用户选定版本；介绍与slogan按原有口白时间展示。

## 当前素材

18个实拍场景、56项素材、10段原速裁片，来源和摘要记录在 `src/current-scenes.json`。目录与Dreaming包含整理进度、保存、查询、来源、对照、批准和再次查询；多设备包含共享设置、跨端查询、来源及三端更新观测。当前真实设置页补充模型选项与更新入口。

画面裁片按字幕时间选择，审批片段保留开始处的批准动作，查询片段突出结果；结束画面继续停留供阅读。实际源时段见 `review/current-playback-timing.json`。两段PPT实录采用相同原录，已在麒麟V11 LibreOffice 24.2完成放映验证。

## 配音与配乐

30镜配音已经齐备，采用 Azure `zh-CN-YunfengNeural`、语速-5%。原音和词级时间保存在 `raw/audio/`，文本、配置、音频摘要和字幕检查见 `review/current-narration-verified.json`。旁白保持170%线性增益。

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
