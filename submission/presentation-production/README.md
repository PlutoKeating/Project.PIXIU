# PIXIU 宣传片对齐路演稿

2026-09-19：按正式宣传片的内容、要点与顺序重新撰写34页可编辑PPT，设六章可点击目录。正式作品仍只有规定命名目录内的最终PPTX；此目录是内部制作和审阅证据，不增加必交作品。

## 内容依据与版式

依据为499.333秒《演示视频-0.1.12演示增强版》，SHA-256 `8e870f0f53af841c67926ae3120cb101564aca438c23d81214c65ffee228a89f`。使用与成片绑定的实际时间轴，30镜全部按原顺序映射，页脚有成片时间范围，备注保留完整对应口白。采购核算、资料更新、账单、知识管理、可信设备和洞察均采用片中演示。README典型场景仅在与视频一致时采用。

六章：日常资料持续积累、让经验留下来、可信设备共同记忆、记忆使用边界、系统协同、效果与价值。目录指向第3/10/18/23/26/30页，后续32页均可返回目录。章节页、金额主视觉、表单实拍、版本对照、时间轴、台阶、设备桥接、泳道、架构及数据页采用不同组织方式。

联网查阅并应用 [Anthropic 官方PPTX skill](https://github.com/anthropics/skills/blob/main/skills/pptx/SKILL.md) 的版式变化、深浅对比、可编辑图形、逐页渲染与Office校验方法。参考包仅保存在忽略的 `.runtime/skills/pptx/` 中。

## 目录

- `source/video-aligned-plan.md`：当前34页内容与版式计划；`storyboard.md` 为已替代的历史方案。
- `scripts/`：生成、整包拆解、成片抽帧、PDF渲染及验证工具。
- `assets/video-frames/`：成片每镜35%和72%位置的60张完整画面。
- `review/video-aligned/`：成片核验清单、15张逐镜联系表、当前逐镜映射。
- `review/final/`：当前PPT全部部件摘要、逐页文本和元素XML清单。解包缓存 `package/` 忽略提交。
- `review/final-review.md`、`review/validation.json`：当前视觉复核和自动检查结果。
- `render/final/`：34页WPS PDF、1600像素整页图与版式总览。
- `render/项目报告.pptx`：已审阅候选，与源资产及正式稿逐字节一致。
- `source/original.pptx`、`review/original/`、`render/original/`：初始18页稿及历史复核。
- `.venv/`、`.runtime/`、早期候选和中间渲染：忽略提交的本地依赖与缓存。

## 重建与复核

先按仓库说明恢复Git LFS对象。在本目录建立虚拟环境，安装 `requirements.txt`。系统使用ffmpeg抽帧、WPS导出PDF、Poppler渲染；设置 `TMPDIR` 为本目录 `.runtime/tmp`，设置 `PYTHONDONTWRITEBYTECODE=1`。

```bash
submission/presentation-production/.venv/bin/python submission/presentation-production/scripts/extract_video_reference.py
submission/presentation-production/.venv/bin/python build/release/scripts/build-presentation.py
```

前者检查正式视频成员摘要并生成60帧参考，后者重建候选及 `docs/delivery/assets/项目报告.pptx`。必须在WPS中打开新候选，导出全部34页到 `render/final/项目报告.pdf`，随后执行：

```bash
bash submission/presentation-production/scripts/render.sh submission/presentation-production/render/final/项目报告.pdf submission/presentation-production/render/final
submission/presentation-production/.venv/bin/python submission/presentation-production/scripts/validate_deck.py
python3 build/release/scripts/export-documentation.py --check
```

另外使用下载的官方skill校验器 `scripts/office/validate.py` 检查PPTX结构。重建候选不等于视觉通过：必须重新渲染、逐页检查后，再替换正式材料并更新导出清单。目录链接、30镜顺序、完整口白备注、成片及图片摘要由本项目校验器核对。

## 验证边界

产品实拍为公开合成演示。历史Debian兼容环境的50/50召回、15/15偏好准确、24/25冲突处理正确及1000次检索P95约115ms，与当前麒麟原生安装、升级、三端协作验证分开呈现。未新增性能或客户结论。

本次用银河麒麟V11的WPS实际导出并逐页检查。Poppler输出字体类型匹配提示，但全部页面成功渲染；尚未在Microsoft PowerPoint复核。此次只调整PPT及其制作文档和工具，未重新运行产品功能测试。
