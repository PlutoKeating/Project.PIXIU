# PIXIU 消息渲染资源

本目录为 KylinAgent 宿主提供完全离线的消息渲染资源：

- markdown-it 14.1.0：CommonMark、GFM 表格、代码块与链接；
- markdown-it-texmath 1.0.0：美元符号、方括号及 LaTeX 环境公式分隔；
- KaTeX 0.16.22：行内与块级 LaTeX 数学公式；
- Mermaid 10.9.5：流程图、时序图、类图、状态图、思维导图和甘特图等；
- KaTeX WOFF2 字体：公式字形；
- Noto Color Emoji 2.051：包内彩色 Unicode emoji 字形。

四项依赖均使用 MIT License，许可证原文保存在 `licenses/`。运行时页面通过 CSP
关闭网络、远端脚本和任意 HTML 输入，仅允许同包 `qrc:` 资源与受限的 `data:` 图片。
正文优先使用 Noto Sans CJK 文本字体，普通空格保持正文的自然字宽；Unicode emoji
再由 Chromium 字形回退到包内 `Noto Color Emoji`，不依赖目标机 fontconfig 是否接纳
彩色位图字体。字体遵循 SIL Open Font License 1.1。
Mermaid 固定在 10.9.5，以兼容银河麒麟 V11 所带 Qt 5.15 WebEngine 的 JavaScript 引擎。
