# 官网参考研究与设计决策

研究日期：2026-09-08。通过联网读取页面内容与原始 HTML 交叉核对。外部网站会变化，以下描述限于本次观察。

## Landing page

| 参考                                                 | 观察                                           | PIXIU 的取舍                                               |
| ---------------------------------------------------- | ---------------------------------------------- | ---------------------------------------------------------- |
| [OpenAI Codex](https://openai.com/zh-Hans-CN/codex/) | 产品定位领先，按实际任务解释价值，产品入口清楚 | 首屏一句核心价值，下载和入门双入口，后续分层介绍能力       |
| [MiMo Code](https://mimo.xiaomi.com/coder)           | 简短定位、直接安装入口、分块解释产品能力       | 保持简洁导引，安装入口跳到实时下载页，不复制固定安装命令   |
| [Kimi Code](https://www.kimi.com/code)               | 聚焦上手与工作流，使用可视化终端内容帮助理解   | 用可操作记忆流程替代纯宣传大图，不使用第三方截图或品牌文案 |

视觉方向：暖白背景、墨色标题、项目科技蓝、细分割线和较大留白。延续现有三节点图标，用对等设备结构表达去中心化记忆。没有复制参考站的商标、图像、客户名单或评价。

## 文档框架的事实核查

### Kimi：VitePress

[文档首页](https://www.kimi.com/code/docs/) 原始 HTML 可见 `vitepress`、`VitePress` 与 `VPDoc`/`VPNav` 标记，加载 `/code/docs/assets/app.*.js`。页面提供分组侧栏、页内目录、搜索与上一页/下一页。

### MiMo：Rspress

[文档首页](https://mimo.xiaomi.com/mimocode/start) 的 HTML 明确含 `meta name="generator" content="Rspress v1.46.2"`，并加载 `lib-react`、`lib-router` 分块。此处有生成器证据，不只是根据视觉推测。其章节按开始使用、核心操作、配置、定制和参考组织。

[Rspress 官方介绍](https://www.rspress.dev/guide/start/introduction)说明它是基于 React/Rsbuild 的静态站生成器，支持 MDX、搜索与主题。

### 本站：VitePress + Vue

采用 VitePress 的稳定线，复用默认文档布局、中文本地搜索、目录、代码高亮和主题，首页使用自定义 Vue 页面。比在两个站点之间维护不同框架更适合这个独立静态目录。

数学公式使用 VitePress 的 MathJax 扩展；Mermaid 通过自定义代码围栏和按需加载组件渲染，支持流程、时序、状态和思维导图。另接入脚注和任务列表。依据：[VitePress Markdown 扩展](https://vitepress.dev/guide/markdown)、[主题扩展](https://vitepress.dev/guide/extending-default-theme)。

## 内容证据优先级

本任务发现根 README 的独立窗口、物理遗忘和历史指标描述，与最新架构及交付手册存在不一致。官网依据较新的 `docs/ARCHITECTURE.md`、`docs/API.md`、`docs/delivery/USER_MANUAL.md`、`docs/delivery/DEPLOYMENT_GUIDE.md` 与截图素材索引，不扩大未验收结论。

当前正式桌面素材索引为空。因此网站采用图表、可操作网页教学示例，以及该示例的真实浏览器截图，显式说明未连接后端、SDK 或设备。后续取得同版桌面实拍后，可以追加真正的操作截图，不能把当前示例重新标成软件实拍。

## 动态发布原则

使用 GitHub REST Releases 的最新正式版端点与分页列表，保持发布者内容为唯一版本事实源。结构性 UI 文案可固定，版本相关名称、描述和附件全部来源于实时响应。GitHub 公开 CORS 暴露 `Link` 和限流头，允许纯静态 Pages 站点完成分页和状态显示。

参考：[GitHub Releases API](https://docs.github.com/en/rest/releases/releases)、[GitHub CORS](https://docs.github.com/en/rest/using-the-rest-api/using-cors-and-jsonp-to-make-cross-origin-requests)。
