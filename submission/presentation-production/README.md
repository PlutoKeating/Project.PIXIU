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

按用户提供的 `reference/ABC公司产品宣传路演PPT.pptx` 制作可编辑试作稿；最新版本在用户手动美工修订稿上调整为34页。参考稿20页已全部转换成1600×900整页图片并逐页观看。复用原稿背景、渐变面板、发光展台、弧形装饰及两张科技意境图，重新绘制 PIXIU 的设备、架构、检索和同步图，嵌入仓库原始界面实拍。根据用户美术反馈，保留完整轨道卡片、图表装饰与源主题色，采用顶部框饰、横幅、左侧大字、全景与图表组合等不同构图；主标题统一为短语。青蓝立体记忆核心由内置 imagegen 生成，作为概念插图使用，见 [插图与提示词](source/memory-core-prompt.md)。正文与章节根据原31页内容重组，保留测试环境和未验证范围。

- [试作 PPTX](render/abc-trial/PIXIU项目报告-科技风试作版.pptx)、[审阅 PDF](render/abc-trial/PIXIU项目报告-科技风试作版.pdf)、[34页总览](render/abc-trial/overview.png)。
- `render/reference/`：参考稿 PDF 与全部20页整页图；`render/abc-trial/`：试作 PDF 与全部34页整页图。
- [逐页设计与复核记录](review/abc-style-review.md)；`review/abc-trial-manifest.json` 记录输入摘要、源页面映射和复制元素；`review/abc-trial-validation.json` 记录检查及渲染摘要。

本次试作使用 LibreOffice 26.2.4.2 导出 PDF，Poppler 26.01.0 渲染，字体为 Microsoft YaHei。尚未在 WPS 或 Microsoft PowerPoint 中另行打开试作稿验证；原31页正式稿和导出入口保持原有版本。参考文件及试作仅供内部比较，不加入正式作品目录。

```bash
submission/presentation-production/.venv/bin/python submission/presentation-production/scripts/build_reference_deck.py
libreoffice -env:UserInstallation=file:///tmp/pixiu-abc-trial-lo --headless --convert-to pdf --outdir submission/presentation-production/render/abc-trial submission/presentation-production/render/abc-trial/PIXIU项目报告-科技风试作版.pptx
bash submission/presentation-production/scripts/render.sh submission/presentation-production/render/abc-trial/PIXIU项目报告-科技风试作版.pdf submission/presentation-production/render/abc-trial
submission/presentation-production/.venv/bin/python submission/presentation-production/scripts/validate_reference_deck.py
```

参考稿首次导出可用同一 LibreOffice 命令，将输入替换为 `reference/ABC公司产品宣传路演PPT.pptx`、输出目录替换为 `render/reference/`，再用 `render.sh` 渲染。安装依赖仍使用本目录 `requirements.txt`；PPTX、PDF、PNG 通过仓库 Git LFS 管理，虚拟环境和临时文件继续忽略。

## 当前试作结构与可重建来源

当前34页试作包含六个章节标题页：3“场景需求与使用背景”、6“产品定位与方案架构”、9“两大核心功能亮点”、14“技术架构与实现方案”、24“真实操作案例”、31“服务模式与商业探索”。新增的四页直接复用已认可技术章节页的背景、原生形状、字体效果与布局。34页均有页码，25页正文有章节导航。

功能部分为10“两大亮点”→11“记忆共享，分布互连”→12“自动记忆，持续整合”→13“场景示例 · 账单检索”。记忆共享页补充用户配对与授权、共享同步和换设备复用；账单页说明家庭开销核对场景、用户操作、实现能力与所得价值，保留原始截图和本例合计。偏好演进页、验证结果与待测范围页已按用户要求删除。安全、部署、任务循环继续相邻，对应21—23页。

`source/user-refined-20260915.pptx` 保存用户手动美工修订的32页原件，SHA-256 为 `08fac263452d86fcb46278c71332272d775878b087e7545fef648a853f08fa71`；相邻 manifest 保存原来源映射。构建入口调用 `reorder_refined_deck.py`，由 `refine_explanations.py` 执行限定的正文补充和章节复制。没有新手动修改的页保留原始包与原生形状；如果输出存在未归档的手动变化，构建会停止，避免覆盖。

验证包含34页顺序与主题、导航和页码、显式删除记录、真实截图字节、章节版式复制，以及本次授权修改范围之外的逐形状XML一致性。依赖沿用现有 python-pptx、lxml、LibreOffice 和 Poppler，无新增运行或发布依赖。原有正式31页资产不变。具体复核见 `review/abc-style-review.md`。

## 当前真实截图版

已检查全部34页，20页配置完整产品窗口与标注，覆盖产品定位、两大亮点、账单场景、主要技术说明及第05部分操作案例。三端共享采用本机三台麒麟虚拟机的原生4K来源截图；Dreaming审批、账单和星河活动采用已有同版真实实录。第23页保留对齐的四步流程，第30页改为三台独立桌面并列、等宽等距展示。

逐页取舍、证据边界与采集条件见 [产品截图审计](review/product-screenshot-audit.md)。生成流程由 `reorder_refined_deck.py` 调用 `product_screenshots.py`；清单记录每张原始图片的摘要、裁切与页面位置，验证同时检查实际嵌入关系。制作依赖及现有重建命令保持一致，原始 PNG 通过 Git LFS 管理。

### 完整窗口与截图标注修订

全34页已复核，其中20页的软件截图改为完整应用窗口或完整桌面，取消独立文字条、按钮条拼贴。图下添加图注，关键位置使用可编辑红框；三端页使用三个独立截图，等宽、等距排列。详见[截图审计](review/product-screenshot-audit.md)。

原始录屏抽帧可运行 `python scripts/extract_full_windows.py`，使用现有 FFmpeg，不裁切或重绘像素；实时采集源 PNG 只校验摘要。完整来源和时间点记录于 `source/full-window-captures/manifest.json`。重建、PDF渲染与验证仍使用上方命令。

图注统一为一句简短陈述，不含括号或标注方式说明，每条最多一个逗号；保留图号及可编辑红框。

## 当前多版式修订

最新输入为 `source/user-cover-closing-20260915.pptx`，完整保留用户本轮修改的封面和尾页。19个正文页根据内容重新设计，直接复制ABC原稿的原生异形底框、渐变卡片、弧面和光效；第25页重叠文字改为时间地点、预算与流程的独立区域。

原有构建/验证命令不变，入口自动选择 `build_varied_deck.py` / `validate_varied_deck.py`；版式维护于 `scripts/varied_layouts.py`。无新依赖。此前“统一窗口配右侧说明”的记录属于旧轮次，当前逐页设计与保护范围以[本轮复核](review/product-screenshot-audit.md)为准。未来若用户再次手动编辑，必须先归档最新文件，构建保护检查会阻止覆盖。

### 六页讲述衔接与无备注版本

第 7、11、12、13、15、25 页补充场景、用户操作、系统处理与后续用途，保留不同版式和完整软件截图。设备按书房台式机、客厅功能机、出差笔记本标注；账单先显示合计标题，再以同一行同样加粗显示金额和元。自动整合卡片统一上边距和正文基线。

构建入口调用 `remove_slide_notes.py` 删除全部备注页、备注母版及关系引用，归档源文件保持不变。校验新增无备注与关键文案检查，无新增依赖。

## 2026-09-15：36页交付版定点修订（当前权威）

本轮完整读取并归档用户直接编辑的正式交付版：`source/user-submission-20260915-36pages.pptx`，输入 SHA-256 为 `03883a5543085a66d9a6e2afe1943b32e848cbec636770a25f3fcf22932819fa`。当前权威是 submission 两层 603821 同名目录内的 `项目报告.pptx`；本页上方31/34页构建记录与 `render/` 旧候选均为历史版本，不可覆盖当前正式稿。

- 第6页：保留全部原生形状、顺序、位置和尺寸；替换 Agent 领域文案，以及三份政策的名称、机关、日期、截图和解读。页码复用现有页脚形状，无新增或删除页面元素。
- 第12页：保留三张独立实拍及其对应红框；增加每端 Agent / PIXIU 本地记忆模块、双向对等连线与离线重连路径。
- 第25页：在左下补充结构化记忆、持续整合、共享与上下文三项工程说明；原论文表与图片保留。
- 按物理页序校准02—35页的可见页码。封面及结束页沿用原来的无页码设计，仍计入36页总数。

重建本轮修订必须使用以下入口并指定**不存在的候选路径**；脚本不会覆盖已有文件。依赖沿用当前 requirements.txt、LibreOffice 和 Poppler，无新增依赖或产品构建变化。

```bash
submission/presentation-production/.venv/bin/python submission/presentation-production/scripts/update_submission_deck.py --output /tmp/pixiu-submission-candidate.pptx
```

脚本从归档的36页用户原件进行包级定点修改，保留其余包部件。候选需重新渲染、复核后才能更新正式文件。验证及版本摘要见 [36页修订复核](review/submission-36page-review.md) 和 `review/submission-36page-validation.json`。完整36页文本见 `review/submission-36page-text.md`。

## 当前第12页：立体终端三角构图

用户确认写回三角形终端版本后，仅替换最新正式文件中的 `ppt/slides/slide12.xml`。上方为书房台式机、左下为客厅一体机、右下为随身笔记本；机身、支架、键盘、底座与双向连线为可编辑原生图形，屏幕使用原始实拍。

本轮以 `source/user-before-triangle-20260915.pptx` 保存写回前的最新用户文件，包括用户同时编辑的第25页。其余35页及全部其他包部件与该备份逐字节一致；总页数36、页码12保持。验证摘要见 `review/triangle-merge-validation.json`，[第12页预览](render/submission-current/triangle-page12.png)已通过LibreOffice渲染检查。前一轮36页PDF、总览与验证记录为历史快照，不包含本次三角形构图及用户随后对第25页的编辑。

制作脚本沿用现有 python-pptx/lxml 依赖，无新增依赖或产品构建配置变化。以下命令从本轮用户备份生成独立候选，禁止覆盖已有输出；正式写回使用最新文件的包级合并及写入前版本核验。

```bash
submission/presentation-production/.venv/bin/python submission/presentation-production/scripts/triangle_devices.py --source submission/presentation-production/source/user-before-triangle-20260915.pptx --output /tmp/pixiu-triangle-candidate.pptx
```

## 当前第19—21页：记忆、冲突与同步逻辑图

用户再次编辑后的正式文件作为本轮输入，已备份为 `source/user-before-logic-diagrams-20260915.pptx`。仅替换三处指定文字区域：

- 第19页：短／中／长期状态节点，带压缩、会话切换／结束、长期保留选择的转换条件，以及长期记忆检索回到任务的虚线回路。
- 第20页：版本汇聚、版本向量判断、因果更新／并发LWW分支、一致副本；另一侧为新旧知识比较后进入更新／合并／人工确认分支。两层处理对象保持区别。
- 第21页：Gossip分发到对端与ACK回传；本机／对端摘要的缺失操作示例及补齐、CRDT合并。

全部图标、节点和连接线均为PowerPoint原生可编辑元素。三页截图、导航、图注及页码均保留；其余33页和所有其他包部件逐字节不变。写回前重新校验当前文件，防止覆盖并行编辑。检查摘要见 `review/logic-diagrams-validation.json`；[第19页](render/logic-diagrams/page-19.png)、[第20页](render/logic-diagrams/page-20.png)、[第21页](render/logic-diagrams/page-21.png)已用LibreOffice导出并以1800像素检查，无新增遮挡。未另在WPS或Microsoft PowerPoint中验证。此前审阅PDF为历史快照。

构建采用现有依赖，不改产品构建或部署配置；独立候选命令如下，已有输出不会被覆盖：

```bash
submission/presentation-production/.venv/bin/python submission/presentation-production/scripts/logic_diagrams.py --source submission/presentation-production/source/user-before-logic-diagrams-20260915.pptx --output /tmp/pixiu-logic-candidate.pptx
```

## 第19—21页图示质感修订（当前版本）

在最新正式稿上重绘三页图示，采用渐变材质、悬浮底座、分层图标、明暗边缘与细线通道；第19页为错层记忆阶梯，第20页为双层决策通道，第21页为设备分发与差异操作块。逻辑关系保持，全部为可编辑原生图形。

写回前备份为 `source/user-before-logic-art-20260915.pptx`。仅三个 slide XML 发生变化，其余33页及其他包部件逐字节保持；94个受保护元素原样保留，第20页两个既有背景仅调整渐变。36页总数及02—35页可见页码复核通过。验证见 [检查记录](review/logic-art-validation.json)，预览：[第19页](render/logic-art/page-19.png)、[第20页](render/logic-art/page-20.png)、[第21页](render/logic-art/page-21.png)。已检查LibreOffice实际渲染，未在WPS或Microsoft PowerPoint中验证。

使用现有依赖，无新增依赖或产品编译、部署配置变动；候选构建入口为：

```bash
submission/presentation-production/.venv/bin/python submission/presentation-production/scripts/refine_logic_art.py --source submission/presentation-production/source/user-before-logic-art-20260915.pptx --output /tmp/pixiu-logic-art-candidate.pptx
```

该入口针对本轮归档输入，不可用旧归档覆盖用户之后的正式文件。正式写回须比较最新文件，对目标页有并行修改时先合并，并在原子替换前重新核验版本。

## 第19—21页增加简短导读（当前版本）

每页标题下保留两句介绍，依次说明分阶段记忆及复用、副本差异与内容矛盾的分层处理、可信设备在线传播及重连补齐。第19页对截图和图示等比缩放留出文字区；第20页下移决策通道、等比缩放截图并下移审批说明；第21页扩展既有导读。原生图形、截图、原有图示文字均保留。

本轮输入备份为 `source/user-before-logic-introductions-20260915.pptx`，仍以正式交付文件为权威。仅修改第19—21页XML，其余包部件逐字节相同；36页总数与页码通过复核，三页LibreOffice渲染检查通过，未在WPS或Microsoft PowerPoint复核。详见 [验证记录](review/logic-introductions-validation.json)；预览：[第19页](render/logic-introductions/page-19.png)、[第20页](render/logic-introductions/page-20.png)、[第21页](render/logic-introductions/page-21.png)。

沿用既有依赖，无新增依赖、产品构建或部署配置变化。生成候选命令如下；写回仍需与最新正式文件比较，保留用户并行编辑。

```bash
submission/presentation-production/.venv/bin/python submission/presentation-production/scripts/add_logic_introductions.py --source submission/presentation-production/source/user-before-logic-introductions-20260915.pptx --output /tmp/pixiu-introductions-candidate.pptx
```
