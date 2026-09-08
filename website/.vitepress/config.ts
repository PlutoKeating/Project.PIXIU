import { defineConfig } from 'vitepress';
import { loadEnv } from 'vite';
import footnote from 'markdown-it-footnote';
import tasks from 'markdown-it-task-lists';
const env = { ...loadEnv('', process.cwd(), ''), ...process.env };
const repo = env.VITE_GITHUB_REPOSITORY || 'PlutoKeating/Project.PIXIU';
const origin = env.VITE_SITE_URL?.replace(/\/$/, '');
export default defineConfig({
  lang: 'zh-CN',
  title: 'PIXIU · 貔貅',
  description:
    '让记忆，随你而行。面向银河麒麟的去中心化 Agent 记忆系统，让知识与偏好在可信设备之间相通。',
  cleanUrls: true,
  srcExclude: ['README.md', 'RESEARCH.md', 'tests/**', 'test-results/**', 'playwright-report/**'],
  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/logo.svg' }],
    ['meta', { name: 'theme-color', content: '#f8f7f4' }],
    ['meta', { property: 'og:type', content: 'website' }],
  ],
  ...(origin ? { sitemap: { hostname: origin } } : {}),
  transformHead({ pageData }) {
    if (!origin) return [];
    const path = pageData.relativePath.replace(/index\.md$/, '').replace(/\.md$/, '');
    return [['link', { rel: 'canonical', href: `${origin}/${path}` }]];
  },
  markdown: {
    math: true,
    image: { lazyLoading: true },
    config(md) {
      // VitePress bundles its own markdown-it types; the plugin uses the same runtime API.
      footnote(md as unknown as Parameters<typeof footnote>[0]);
      md.use(tasks);
      const fence = md.renderer.rules.fence!;
      md.renderer.rules.fence = (tokens, idx, options, env, self) => {
        if (tokens[idx].info.trim() === 'mermaid') {
          return `<Diagram source="${md.utils.escapeHtml(encodeURIComponent(tokens[idx].content))}" />`;
        }
        return fence(tokens, idx, options, env, self);
      };
    },
  },
  themeConfig: {
    logo: '/logo.svg',
    siteTitle: 'PIXIU',
    skipToContentLabel: '跳至正文',
    notFound: {
      title: '这一页，还没有记忆。',
      quote: '地址可能有误，或内容已经移动。回到首页继续探索 PIXIU。',
      linkLabel: '返回首页',
      linkText: '返回首页',
    },
    nav: [
      { text: '产品', link: '/' },
      { text: '使用文档', link: '/docs/' },
      { text: '版本记录', link: '/releases' },
      { text: '下载', link: '/download' },
    ],
    socialLinks: [{ icon: 'github', link: `https://github.com/${repo}` }],
    sidebar: {
      '/docs/': [
        {
          text: '认识 PIXIU',
          items: [
            { text: '产品概览', link: '/docs/' },
            { text: '交互演示', link: '/docs/start/playground' },
          ],
        },
        {
          text: '开始使用',
          items: [
            { text: '安装与启动', link: '/docs/start/install' },
            { text: '连接模型', link: '/docs/start/models' },
            { text: '第一次记忆', link: '/docs/start/first-memory' },
          ],
        },
        {
          text: '使用手册',
          items: [
            { text: '会话与工具', link: '/docs/guide/agent' },
            { text: '检索、编辑与证据', link: '/docs/guide/memory' },
            { text: '偏好与冲突', link: '/docs/guide/preferences' },
            { text: '多设备同步', link: '/docs/guide/sync' },
            { text: '采集与隐私', link: '/docs/guide/privacy' },
            { text: '安全遗忘', link: '/docs/guide/forget' },
            { text: '更新与恢复', link: '/docs/guide/updates' },
          ],
        },
        {
          text: '理解与参考',
          items: [
            { text: '记忆如何工作', link: '/docs/concepts/architecture' },
            { text: 'API 与配置', link: '/docs/reference/api' },
            { text: '故障排查', link: '/docs/reference/troubleshooting' },
            { text: '富 Markdown 示例', link: '/docs/reference/markdown' },
          ],
        },
      ],
    },
    outline: { level: [2, 3], label: '本页内容' },
    docFooter: { prev: '上一页', next: '下一页' },
    sidebarMenuLabel: '文档目录',
    returnToTopLabel: '回到顶部',
    darkModeSwitchLabel: '外观',
    lightModeSwitchTitle: '切换浅色',
    darkModeSwitchTitle: '切换深色',
    search: {
      provider: 'local',
      options: {
        locales: {
          root: {
            translations: {
              button: { buttonText: '搜索文档', buttonAriaLabel: '搜索文档' },
              modal: {
                noResultsText: '未找到相关内容',
                resetButtonTitle: '清除搜索',
                footer: { selectText: '选择', navigateText: '切换', closeText: '关闭' },
              },
            },
          },
        },
      },
    },
    footer: {
      message: '聚财守忆 · 让每一台设备的记忆，彼此相通。',
      copyright: 'PIXIU · 基于开放技术构建',
    },
  },
});
