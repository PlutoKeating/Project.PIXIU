# PIXIU 项目官网

`website/` 是独立的 VitePress 静态站：根路径是产品 landing page，`/docs/` 是分类手册，`/download` 和 `/releases` 在浏览器中读取 GitHub 公开发布信息。不依赖 PIXIU 后端、Qt、Python、Docker 或官方 SDK submodule。

## 目录隔离约束

网站代码、文档、部署配置、测试、素材及本地缓存必须全部位于 `website/` 内。不得在仓库其他目录、根 README、应用界面或全局配置中增加网站入口或网站存在的说明；删除本目录后，当前工作树的其他文件不应留下本站相关内容。此约束同样适用于后续维护。

所有网站命令（包括 Wrangler）均从本目录执行；部署缓存由本目录 `.gitignore` 忽略。不得在根目录添加网站专用忽略规则、工作流或依赖。平台项目配置在本文件记录，外部技术参考及 GitHub API 地址属于第三方数据来源，不是本站备用域名。

## 本地运行

使用 Node.js 22 或更高版本：

```bash
cd website
npm ci
npm run dev
```

验证与预览：

```bash
npm run typecheck
npm run format:check
npm run build
npm run preview
```

浏览器回归：

```bash
npx playwright install chromium
npm test
```

`npm test` 检查已构建产物，并自动启动本地预览。受控 API 响应仅存在于 `tests/`，不会进入发布产物。真实 GitHub 可访问性需另外验证；测试通过不代表 Cloudflare 已部署。

## Cloudflare Pages 配置

在 Cloudflare 的 **Workers & Pages → 创建应用 → Pages → 连接 Git** 中绑定当前 GitHub 仓库。使用 Pages 的 Git 集成静态构建，不需要 Worker、Functions、Wrangler 部署命令或后端服务。

| 字段                              | 填写内容                                                          |
| --------------------------------- | ----------------------------------------------------------------- |
| 仓库                              | 当前 `Project.PIXIU` GitHub 仓库                                  |
| 生产分支                          | `main`（确保网站提交已由维护者推送）                              |
| 框架预设                          | `VitePress`，或 `None` 后手动填写以下字段                         |
| 根目录 / Root directory           | `website`                                                         |
| 构建命令 / Build command          | `npm ci && npm run build`                                         |
| 输出目录 / Build output directory | `.vitepress/dist`                                                 |
| 环境变量                          | `NODE_VERSION=22`                                                 |
| 环境变量                          | `SKIP_DEPENDENCY_INSTALL=true`（安装已显式包含在构建命令中）      |
| 可选公开变量                      | `VITE_GITHUB_REPOSITORY=PlutoKeating/Project.PIXIU`（默认已配置） |

输出目录相对于 `website`，**不要再次填写 `website/.vitepress/dist`**。根目录 `base` 为 `/`，打开域名直接进入 landing page。

唯一生产域名为 <https://pixiu.arr2018.dpdns.org>，在 `.vitepress/config.ts` 中统一配置。所有构建的 sitemap 与 canonical 均指向该域名，不接受环境变量覆盖。

Pages 可能先自动安装依赖；设置 `SKIP_DEPENDENCY_INSTALL=true` 后仅由构建命令执行一次锁文件安装。当前配置不依赖平台预装 npm 包，也不把开发机 `node_modules` 上传。

建议构建监视包含路径设为 `website/*`，使应用其他模块修改不会无意义重建官网。发布数据在浏览器现场获取，GitHub Release 新增或修改不需要重建网站。

本站资源全部在 `website/` 内，构建不读取 `third_party/`。仓库检出阶段如因 Gitee 子模块访问失败而中止，应先核对 Pages 克隆日志；它发生在 npm 构建之前，修改输出目录不能修复外部检出失败。

Pages「自定义域」已由维护者绑定 `pixiu.arr2018.dpdns.org`，部署后应检查域名状态和 HTTPS。无需添加把所有路由重写到首页的 SPA 通配规则；VitePress 已生成各页面和 `404.html`。

平台依据：[VitePress 部署](https://developers.cloudflare.com/pages/framework-guides/deploy-a-vitepress-site/)、[构建目录](https://developers.cloudflare.com/pages/configuration/build-configuration/)、[构建环境变量](https://developers.cloudflare.com/pages/configuration/build-image/)、[构建监视路径](https://developers.cloudflare.com/pages/configuration/build-watch-paths/)。

## 发布信息的数据规则

公共仓库身份集中在 `.vitepress/theme/lib/site.ts`。这属于数据源配置，不是硬编码版本或下载地址。

- 最新正式版：浏览器 `fetch GET /repos/{owner}/{repo}/releases/latest`，采用 GitHub 的 latest 定义，不按字符串或本地常量猜版本。
- 历史：`GET /repos/{owner}/{repo}/releases?per_page=10&page=N`，按 API 顺序显示，使用公开 CORS `Link` 头控制「加载更多」，默认包含预发布，可筛选。
- 名称、标签、日期、发布说明、附件名称/大小/digest/下载 URL 全来自响应；不维护静态 release JSON、下载镜像、固定安装包地址或构建期版本快照。
- 页面仅固定结构性标题、按钮与状态提示，不固定任何版本的发布文案。没有说明或附件时明确展示缺失，不生成补充发布内容。
- 15 秒请求超时，支持取消、失败重试、限流恢复时间、空历史、无正式版、无附件和异常数据。失败刷新时明确标注上次成功获取的数据尚未刷新。
- 每次进入页面及显式刷新重新请求，不用持久缓存掩盖过期数据。网站没有后台轮询或向访问者索要 Token 的流程。
- 使用 GitHub CORS 公开 API，不设置 GitHub Token。`VITE_*` 都是公开变量，不存放秘密。未认证请求受 GitHub 每 IP 小时额度等限制；浏览器到 GitHub 的网络可达性仍是必要条件。
- 返回的下载链接必须为当前仓库 GitHub Releases HTTPS 路径。发布说明使用 MarkdownIt（关闭 HTML）与 DOMPurify，不编译 Vue、不执行脚本；远端图片被移除以避免跟踪加载。可信手册与远端发布文本是不同渲染路径。

API 依据：[Releases](https://docs.github.com/en/rest/releases/releases)、[跨域请求和公开响应头](https://docs.github.com/en/rest/using-the-rest-api/using-cors-and-jsonp-to-make-cross-origin-requests)、[请求额度](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)。

## 内容和视觉维护

- `.vitepress/config.ts`：导航、章节、中文搜索、标题与富 Markdown 配置。
- `.vitepress/theme/components/`：首页、网页演示、发布页、Mermaid 绘制。
- `.vitepress/theme/style.css`：浅深主题、响应式和焦点样式。
- `docs/`：16 篇面向使用者的分类文档，包含流程图、时序图、思维导图、公式、表格、脚注、任务列表、代码组与可操作演示。
- `public/media/memory-playground.png`：本网站交互组件的真实浏览器截图，不是桌面软件实拍。使用合成数据，不取代仓库中待补的原生截图与验收证据。
- `public/logo.svg`：复制自项目现有图标 `frontend/resources/icons/pixiu.svg`，后续品牌调整时同步。
- `RESEARCH.md`：参考页面的可验证技术事实与设计取舍。

新增文章后在 sidebar 中登记，执行构建以检查内部链接。不要在官网写入特定机器路径、真实私人地址、模型密钥或未经核实的验收结论。

截图复现：启动站点，用浏览器打开首页，保持默认合成数据，截取 `.memory-demo` 元素即可。示例素材不需要 Git LFS，PNG 体积较小；依赖、构建缓存和测试报告已在 `website/.gitignore` 中忽略。

## 依赖维护

VitePress 使用稳定版本，依赖由 `package-lock.json` 锁定。`overrides` 将其旧 Vite 依赖升级至兼容的 6.4.3 修复线，并将 MathJax 间接 XML 解析器升级至 0.9.12 修复线；升级后需运行构建、类型检查与浏览器回归。Mermaid 只在图表组件挂载时动态加载，首屏不会请求整套绘图引擎。部分 Mermaid 图布局分块较大，构建可能给出 chunk size 提示，不影响静态部署。

## 部署后核对

1. 根域直接打开首页，手机导航能进入文档。
2. 直接刷新 `/docs/guide/sync`、`/download` 和 `/releases`，均可访问。
3. 搜索中文「遗忘」，检查结果跳转与章节目录。
4. 查看公式、Mermaid 思维导图与截图，切换浅深主题。
5. 下载与历史显示真实 GitHub 数据，逐项核对附件。临时阻断 GitHub 请求时应出现错误状态。
6. 未知路径返回 404 页面；检查 sitemap 和 canonical 均使用唯一生产域名。

已按维护者授权推送官网提交，并创建 GitHub 集成项目 `pixiu-website`，绑定 `PlutoKeating/Project.PIXIU` 的 `main`。唯一生产地址为 <https://pixiu.arr2018.dpdns.org>；仅 `website/*` 变动自动触发生产构建，预览分支部署和 PR 评论关闭。自定义域名已由维护者绑定。

## 本地验证记录

本次在 Node.js 24 / Chromium 环境验证：生产构建、Vue/TypeScript 类型检查、Prettier 检查和 18 项 Playwright 回归通过（含全部页面 canonical 与 sitemap 的唯一生产域名检查）。浏览器实际请求 GitHub 成功，读取了公开正式发布及其附件，未出现 JavaScript 运行错误；375px、768px、1440px 布局与中文搜索、数学公式、Mermaid 渲染已检查。依赖安装审计为 0 个已知漏洞。

静态产物包含首页、下载、历史、16 篇手册与 404 页；维护文档、测试用例与测试报告不进入发布目录。以上为部署前的本地验证，线上状态需另行核对 Pages 部署记录与实际访问；银河麒麟桌面截图尚未验证。

## 配音试听选择

主页顶栏“配音试听”打开 `/voice-audition.html`。独立页面位于
`public/voice-audition.html`，12 份已生成的中文普通话男声默认风格音频位于
`public/audio/voices/`，文件名就是 Azure 音色 ID。音频按需加载，复用现有素材。

第一轮可勾选任意多个音色；结束后仅显示入围候选。第二轮可移除或恢复候选，
保留 1–3 个时才可提交。最终名单显示音色名称和 ID，供成员截图发送。
选择只保存在当前页面内存中，刷新后重置；没有结果上传、统计或服务端接口。

导航使用 `target: '_self'`，以完整页面导航打开静态 HTML。部署沿用现有
VitePress public 资源复制流程，无新增依赖或部署步骤。
`tests/voice-audition.spec.ts` 覆盖选择边界、恢复操作、音频资源和移动端布局。
