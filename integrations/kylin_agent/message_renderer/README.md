# PIXIU 消息渲染资源

本目录为 KylinAgent 宿主提供完全离线的消息渲染资源：

- markdown-it 14.1.0：CommonMark、GFM 表格、代码块与链接；
- markdown-it-texmath 1.0.0：美元符号、方括号及 LaTeX 环境公式分隔；
- KaTeX 0.16.22：行内与块级 LaTeX 数学公式；
- Mermaid 11.12.0：流程图、时序图、类图、状态图、思维导图和甘特图等；
- KaTeX WOFF2 字体：公式字形。

四项依赖均使用 MIT License，许可证原文保存在 `licenses/`。运行时页面通过 CSP
关闭网络、远端脚本和任意 HTML 输入，仅允许同包 `qrc:` 资源与受限的 `data:` 图片。
Unicode emoji 由 Chromium 字形整形与系统 `Noto Color Emoji` 字体完成。
