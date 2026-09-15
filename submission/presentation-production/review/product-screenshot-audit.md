# 本轮版式复核与截图审计

## 最新文件与保护范围

用户本轮修改了封面和尾页，最新34页文件已完整归档为 `source/user-cover-closing-20260915.pptx`，SHA-256为 `a88c4bb639c7aba6e6b834672a710b5ccd26d589c3ca72c1cf2760d188af0a66`。当前生成直接以该文件的整个PPTX包为基底，避免从旧版重新生成而丢失用户美工。封面、尾页、其他未改页、母版与关联素材均保留原始字节。19个正文页仅替换授权的正文区域，顶部主题、导航、页码保留。

## 排版调整

第25页不再用固定高度的说明列表。日期、时间地点、预算和操作流程分区排列，预算与下一段标题之间设分隔线与留白，修复原三行正文挤入下一标题的问题。

参考ABC原稿第3、7、11、12页的原生渐变卡片、半透明弧面、异形舞台和底部投影，按内容分别采用双亮点舞台、三端并列、纵向步骤、金额主视觉、横向接入/检索、知识分类网格、阶梯流转、冲突对照、安全分区、恢复数字和活动时间变化等结构。原生形状和光条直接复制，原稿无关正文与公司信息不导入。具体来源页、形状索引与坐标写入构建清单的 `artworks`。

| 页码 | 当前版式 |
|---|---|
| 07 | product stage with feature ribbons |
| 10 | two flagship podiums |
| 11 | three device columns |
| 12 | vertical integration process beside full review |
| 13 | bill total and evidence with lower value cards |
| 15 | three input paths above software settings |
| 16 | knowledge categories and provenance chain |
| 17 | three retrieval lanes feeding result |
| 18 | ascending memory timeline |
| 19 | two conflict layers above approval evidence |
| 20 | online and reconnect swimlanes |
| 21 | security quadrants with permissions window |
| 22 | native platform bands and recovery metric |
| 23 | four-step lifecycle with reverse evidence placement |
| 25 | activity facts above process with full source |
| 26 | cross-session editorial statement |
| 27 | approval comparison with change callout |
| 28 | updated activity outcome with retained budget |
| 30 | three-device verification stage |

## 真实截图与图注

全稿仍为25处完整软件窗口/桌面截图。原始像素、长宽比、来源清单和红框保留，三端素材来自三个独立文件；图注为一句简短陈述，不含括号或标注方法说明，最多一个逗号。软件画面仅证明可见状态，不将设备列表视为实时送达证明，当前记录一致不替代历史并发验证。

## 构建与验证

原有入口 `build_reference_deck.py` 在发现最新归档后调用 `build_varied_deck.py`，版式由 `varied_layouts.py` 生成，复用原有截图嵌入逻辑。验证入口调用 `validate_varied_deck.py`，比对最新归档的非修改包内容、正文以外形状、截图字节、图注规则与34页渲染。依赖仍为现有 python-pptx、lxml、Pillow、LibreOffice、Poppler；无新增产品或构建依赖。

已使用LibreOffice/Poppler整页渲染，逐页总览并重点查看第7、12、13、16、19、21、23、25页，修复长句孤字换行。未另用WPS/PowerPoint打开新版。正式31页资产未修改。
