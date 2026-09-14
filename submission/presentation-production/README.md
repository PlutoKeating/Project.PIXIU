# PIXIU 路演稿制作与复核

2026-09-14：将原18页提交稿重构为31页可编辑路演稿。正式作品仍只有规定命名目录内的最终 PPTX；此目录是内部工程与审阅证据，不增加必交作品。

## 目录

- `source/`：原始 PPTX 备份、31页故事板。
- `scripts/`：生成、完整包拆解、PDF整页渲染和验证工具。
- `assets/`：最初从原稿提取的真实截图备份；当前生成输入优先使用仓库原始截图。
- `review/original/`、`review/final/`：每个包部件的摘要、每页全部文本与元素 XML 清单。解包缓存 `package/` 忽略提交，可随时重建。
- `review/original-review.md`、`review/final-review.md`：逐页视觉与图形语义记录。
- `render/original/`：原18页 WPS PDF 与1600像素整页图。
- `render/final/`：终版31页 WPS PDF 与1600像素整页图。
- `render/项目报告.pptx`：经本次视觉审核的候选，正式稿与其逐字节相同。
- `.venv/`、`.runtime/`、早期候选：忽略提交的依赖、运行时与迭代缓存。

## 重建与复核

先恢复 Git LFS 截图，然后在本目录创建虚拟环境，使用 `requirements.txt` 安装制作依赖。设置 `TMPDIR` 为本目录 `.runtime/tmp`，避免临时文件进入正式交付目录。

```bash
submission/presentation-production/.venv/bin/python submission/presentation-production/scripts/build_deck.py
```

该命令只重建候选与输入清单。通用文档导出入口 `build/release/scripts/build-presentation.py` 会调用它并更新受版本控制的 `docs/delivery/assets/项目报告.pptx`。重建后须再次导出PDF并逐页视觉复核，不能沿用旧的验证摘要。

本次使用银河麒麟 V11 安装的 WPS 演示打开原稿与候选，选择“输出PDF文件”，导出全部页面到本目录。随后执行：

```bash
bash submission/presentation-production/scripts/render.sh submission/presentation-production/render/final/项目报告.pdf submission/presentation-production/render/final
submission/presentation-production/.venv/bin/python submission/presentation-production/scripts/validate_deck.py
python3 build/release/scripts/export-documentation.py --check
```

本次不是用 LibreOffice 渲染；下载尝试中止，未安装该软件。Poppler 对 WPS 嵌入字体给出类型匹配提示，31页均成功渲染，已逐页检查文字与图形。未另在 Microsoft PowerPoint 验证排版。

## 内容与证据边界

README 的林先生家庭账单故事用于需求背景；当前账单截图是九月公开合成记录，不能冒充四月家庭实际消费。完整案例采用星河观测活动同次实录：原文 → 新会话查询 → 更正审批 → 更新查询。

量化页来自2026-08-24 portable基线，保留样本、阈值和统计口径；0.1.12 V11双SDK、47条升级恢复及同宿主三虚拟机实测分别呈现。未测量项不写为已通过。

商业页的三种服务收费方式和试点流程均为待验证设想。仅“存在公开适配与伙伴申请渠道”参考麒麟官方页面，链接保存在第30页备注。无客户、收入、定价或认证承诺。
