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

上述 2026-09-14 的31页正式稿使用 WPS 渲染；当时 LibreOffice 下载尝试中止。Poppler 对 WPS 嵌入字体给出类型匹配提示，31页均成功渲染，已逐页检查文字与图形。未另在 Microsoft PowerPoint 验证排版。

## 内容与证据边界

README 的林先生家庭账单故事用于需求背景；当前账单截图是九月公开合成记录，不能冒充四月家庭实际消费。完整案例采用星河观测活动同次实录：原文 → 新会话查询 → 更正审批 → 更新查询。

量化页来自2026-08-24 portable基线，保留样本、阈值和统计口径；0.1.12 V11双SDK、47条升级恢复及同宿主三虚拟机实测分别呈现。未测量项不写为已通过。

商业页的三种服务收费方式和试点流程均为待验证设想。仅“存在公开适配与伙伴申请渠道”参考麒麟官方页面，链接保存在第30页备注。无客户、收入、定价或认证承诺。

## 2026-09-15：参考稿科技风试作版

按用户提供的 `reference/ABC公司产品宣传路演PPT.pptx` 制作32页可编辑试作稿。参考稿20页已全部转换成1600×900整页图片并逐页观看。复用原稿背景、渐变面板、发光展台、弧形装饰及两张科技意境图，重新绘制 PIXIU 的设备、架构、检索和同步图，嵌入仓库原始界面实拍。根据用户美术反馈，保留完整轨道卡片、图表装饰与源主题色，采用顶部框饰、横幅、左侧大字、全景与图表组合等不同构图；主标题统一为短语。青蓝立体记忆核心由内置 imagegen 生成，作为概念插图使用，见 [插图与提示词](source/memory-core-prompt.md)。正文与章节根据原31页内容重组，保留测试环境和未验证范围。

- [试作 PPTX](render/abc-trial/PIXIU项目报告-科技风试作版.pptx)、[审阅 PDF](render/abc-trial/PIXIU项目报告-科技风试作版.pdf)、[32页总览](render/abc-trial/overview.png)。
- `render/reference/`：参考稿 PDF 与全部20页整页图；`render/abc-trial/`：试作 PDF 与全部32页整页图。
- [逐页设计与复核记录](review/abc-style-review.md)；`review/abc-trial-manifest.json` 记录输入摘要、源页面映射和复制元素；`review/abc-trial-validation.json` 记录检查及渲染摘要。

本次试作使用 LibreOffice 26.2.4.2 导出 PDF，Poppler 26.01.0 渲染，字体为 Microsoft YaHei。尚未在 WPS 或 Microsoft PowerPoint 中另行打开试作稿验证；原31页正式稿和导出入口保持原有版本。参考文件及试作仅供内部比较，不加入正式作品目录。

```bash
submission/presentation-production/.venv/bin/python submission/presentation-production/scripts/build_reference_deck.py
libreoffice -env:UserInstallation=file:///tmp/pixiu-abc-trial-lo --headless --convert-to pdf --outdir submission/presentation-production/render/abc-trial submission/presentation-production/render/abc-trial/PIXIU项目报告-科技风试作版.pptx
bash submission/presentation-production/scripts/render.sh submission/presentation-production/render/abc-trial/PIXIU项目报告-科技风试作版.pdf submission/presentation-production/render/abc-trial
submission/presentation-production/.venv/bin/python submission/presentation-production/scripts/validate_reference_deck.py
```

参考稿首次导出可用同一 LibreOffice 命令，将输入替换为 `reference/ABC公司产品宣传路演PPT.pptx`、输出目录替换为 `render/reference/`，再用 `render.sh` 渲染。安装依赖仍使用本目录 `requirements.txt`；PPTX、PDF、PNG 通过仓库 Git LFS 管理，虚拟环境和临时文件继续忽略。

科技风试作已按最新标注修订主标题位置、案例层级、三设备网状示意和图文间距，移除制作式页脚。逐项记录见 [复核记录](review/abc-style-review.md)。

最新细节版恢复全部32页页码，并在27页正文顶部加入六章节导航与当前分项高亮；封面、目录、章节封面和结尾页不加导航。第8、10、14、17、18、20、28、29页复用参考稿原生异形侧翼、半透明面板与发光底边，部分条形卡片替换为弧光胶囊卡片。构建和验证脚本同步维护，依赖与导出命令不变。

两大主推功能统一为“自动记忆，持续整合”（后台理解与记忆整合，工程名 Dreaming）和“记忆共享，分布互连”（分布式多设备 Agent 记忆共享）。32页科技风稿强化封面、双亮点总览、能力详解、案例验证与结尾的对应关系；目录采集仅作为入口步骤。命名边界见制作目录 `source/feature-naming.md`。本轮无新增依赖，沿用现有构建与渲染脚本。

第3页补充多设备用户背景、三处记忆断点与 PIXIU 的作用，以家庭账单作为示例串起保存、查询和更正，同时明确项目资料、会议记录等通用场景。沿用现有生成与渲染依赖。

第3页保留引入、三设备和总结布局，长文本改用可编辑的分色重点、主动断行及半透明圆顶卡片；统一段落内边距，增强层级和留白。无新增依赖或导出配置。
