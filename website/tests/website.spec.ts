import { test, expect } from '@playwright/test';
const api = 'https://api.github.com/repos/PlutoKeating/Project.PIXIU';
const release = (id: number, prerelease = false) => ({
  id,
  name: `Public release ${id}`,
  tag_name: `test-${id}`,
  body: '## Changes\n\nFetched from API\n\n| Feature | State |\n| --- | --- |\n| Memory | Ready |',
  html_url: `https://github.com/PlutoKeating/Project.PIXIU/releases/tag/test-${id}`,
  published_at: '2026-01-02T10:00:00Z',
  prerelease,
  draft: false,
  assets: [
    {
      id,
      name: `package-${id}.deb`,
      size: 2048,
      digest: null,
      browser_download_url: `https://github.com/PlutoKeating/Project.PIXIU/releases/download/test-${id}/package-${id}.deb`,
    },
  ],
});

test('landing demo changes totals, cancels and confirms forgetting, then resets', async ({
  page,
}) => {
  await page.goto('/');
  await expect(page.locator('h1')).toContainText('随你而行');
  const demo = page.locator('.memory-demo');
  await demo.getByRole('button', { name: '03 更正' }).click();
  await demo.getByLabel('燃气费（元）').fill('200');
  await demo.getByRole('button', { name: '保存更正' }).click();
  await demo.getByRole('button', { name: '02 找回' }).click();
  await expect(demo.locator('.amount')).toHaveText('¥ 478.50');
  await demo.getByRole('button', { name: /查看来源清单/ }).click();
  await expect(demo.locator('.mini-bills')).toContainText('200.00');
  await demo.getByRole('button', { name: '04 遗忘' }).click();
  await demo.getByRole('button', { name: '预览遗忘范围' }).click();
  await demo.getByRole('button', { name: '取消', exact: true }).click();
  await expect(demo.getByRole('button', { name: '确认遗忘' })).toHaveCount(0);
  await demo.getByRole('button', { name: '预览遗忘范围' }).click();
  await demo.getByRole('button', { name: '确认遗忘' }).click();
  await demo.getByRole('button', { name: '02 找回' }).click();
  await expect(demo).toContainText('这条记忆已在演示中隐藏');
  await demo.getByRole('button', { name: /重新体验/ }).click();
  await demo.getByRole('button', { name: '02 找回' }).click();
  await expect(demo.locator('.amount')).toHaveText('¥ 434.50');
});

test('latest release and assets come from fetch and refresh changes content', async ({ page }) => {
  let current = 301;
  await page.route(`${api}/releases/latest`, (route) => route.fulfill({ json: release(current) }));
  await page.goto('/download');
  await expect(page.locator('.release-tag')).toHaveText('test-301');
  await expect(page.locator('.release-notes table')).toContainText('Memory');
  await expect(page.getByRole('link', { name: /package-301.deb/ })).toHaveAttribute(
    'href',
    release(301).assets[0].browser_download_url,
  );
  current = 902;
  await page.getByRole('button', { name: '刷新', exact: true }).click();
  await expect(page.locator('.release-tag')).toHaveText('test-902');
  await expect(page.getByRole('link', { name: /package-301.deb/ })).toHaveCount(0);
});

test('history pagination preserves ordering and filters prereleases', async ({ page }) => {
  await page.route(`${api}/releases?*`, (route) => {
    const second = new URL(route.request().url()).searchParams.get('page') === '2';
    return route.fulfill({
      json: second ? [release(1)] : [release(3, true), release(2)],
      headers: second
        ? {}
        : {
            link: `<${api}/releases?per_page=10&page=2>; rel="next"`,
            'access-control-expose-headers': 'link',
          },
    });
  });
  await page.goto('/releases');
  await expect(page.locator('.release-card')).toHaveCount(2);
  await page.getByLabel('包含预发布').uncheck();
  await expect(page.locator('.release-card')).toHaveCount(1);
  await page.getByRole('button', { name: '加载更多记录' }).click();
  await expect(page.locator('.release-tag')).toHaveText(['test-2', 'test-1']);
  await expect(page.getByRole('button', { name: '加载更多记录' })).toHaveCount(0);
});

test('rate limit gives recovery without invented download links', async ({ page }) => {
  await page.route(`${api}/releases/latest`, (route) =>
    route.fulfill({
      status: 403,
      headers: {
        'access-control-expose-headers': 'x-ratelimit-remaining,x-ratelimit-reset',
        'x-ratelimit-remaining': '0',
        'x-ratelimit-reset': '2000000000',
      },
      json: { message: 'rate limited' },
    }),
  );
  await page.goto('/download');
  await expect(page.getByRole('alert')).toContainText('GitHub 请求额度暂时用尽');
  await expect(page.locator('.asset-list a')).toHaveCount(0);
  await page.unroute(`${api}/releases/latest`);
  await page.route(`${api}/releases/latest`, (route) => route.fulfill({ json: release(4) }));
  await page.getByRole('button', { name: '重试', exact: true }).click();
  await expect(page.locator('.release-tag')).toHaveText('test-4');
});

test('missing stable version and empty history have explicit empty states', async ({ page }) => {
  await page.route(`${api}/releases/latest`, (route) => route.fulfill({ status: 404, json: {} }));
  await page.goto('/download');
  await expect(page.getByRole('alert')).toContainText('未找到公开的正式版');
  await page.route(`${api}/releases?*`, (route) => route.fulfill({ json: [] }));
  await page.goto('/releases');
  await expect(page.locator('.release-state')).toContainText('尚无公开发布记录');
});

test('network failure and missing assets never produce a fabricated package', async ({ page }) => {
  await page.route(`${api}/releases/latest`, (route) => route.abort());
  await page.goto('/download');
  await expect(page.getByRole('alert')).toContainText('无法连接 GitHub');
  await page.unroute(`${api}/releases/latest`);
  await page.route(`${api}/releases/latest`, (route) =>
    route.fulfill({ json: { ...release(5), assets: [], body: null } }),
  );
  await page.getByRole('button', { name: '重试', exact: true }).click();
  await expect(page.locator('.release-card')).toContainText('此版本未附带可下载文件');
  await expect(page.locator('.asset-list a')).toHaveCount(0);
});

test('rejects unexpected asset hosts and untrusted release markup', async ({ page }) => {
  const unsafe = {
    ...release(6),
    assets: [{ ...release(6).assets[0], browser_download_url: 'https://example.com/payload.deb' }],
  };
  await page.route(`${api}/releases/latest`, (route) => route.fulfill({ json: unsafe }));
  await page.goto('/download');
  await expect(page.getByRole('alert')).toContainText('数据格式不符合预期');
  await page.unroute(`${api}/releases/latest`);
  const payload = {
    ...release(7),
    body: '<img src=x onerror="window.pwned=true">\n<script>window.pwned=true</script>\n[bad](javascript:alert(1))\n![tracking](https://example.com/tracker.png)\n{{ window.pwned = true }}',
  };
  await page.route(`${api}/releases/latest`, (route) => route.fulfill({ json: payload }));
  await page.getByRole('button', { name: '重试', exact: true }).click();
  await expect(page.locator('.release-notes')).toContainText('window.pwned');
  await expect(
    page.locator(
      '.release-notes img, .release-notes script, .release-notes a[href^="javascript:"]',
    ),
  ).toHaveCount(0);
  expect(await page.evaluate(() => 'pwned' in window)).toBe(false);
});

test('rich markdown renders math, tables, footnotes, mindmap and sequence diagram', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/docs/reference/markdown');
  await expect(page.locator('.vp-doc table')).toBeVisible();
  await expect(page.locator('mjx-container').first()).toBeVisible();
  await expect(page.locator('.diagram-svg svg')).toHaveCount(2, { timeout: 30000 });
  await expect(page.locator('.footnotes')).toBeVisible();
  await expect(page.locator('.task-list-item')).toHaveCount(3);
  expect(errors).toEqual([]);
});

test('client navigation renders a new diagram and theme switch redraws it', async ({ page }) => {
  await page.goto('/docs/start/install');
  await expect(page.locator('.diagram-svg svg')).toHaveCount(1, { timeout: 30000 });
  await page.locator('.VPSidebar').getByRole('link', { name: '多设备同步', exact: true }).click();
  await expect(page.locator('.diagram-svg svg')).toHaveCount(2, { timeout: 30000 });
  await page.getByRole('switch').first().click();
  await expect(page.locator('html')).toHaveClass(/dark/);
  await expect(page.locator('.diagram-svg svg')).toHaveCount(2);
});

test('Chinese document search returns navigable results', async ({ page }) => {
  await page.goto('/docs/');
  await page.getByRole('button', { name: '搜索文档' }).click();
  const search = page.locator('#localsearch-input');
  await search.fill('遗忘');
  await expect(page.locator('.VPLocalSearchBox .result').first()).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(search).toHaveCount(0);
});

for (const width of [375, 768, 1440]) {
  test(`layout has no page overflow at ${width}px and screenshots are real`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    for (const path of ['/', '/docs/start/playground', '/docs/reference/markdown']) {
      await page.goto(path);
      await expect(page.locator('h1').first()).toBeVisible();
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth,
      );
      expect(overflow, `${path} overflows`).toBe(false);
      if (path.includes('playground'))
        await expect(page.locator('img[src="/media/memory-playground.png"]')).toHaveJSProperty(
          'complete',
          true,
        );
    }
  });
}

test('build includes a static 404 page for Cloudflare routing', async ({ page }) => {
  await page.goto('/404.html');
  await expect(page.getByRole('heading', { name: '这一页，还没有记忆。' })).toBeVisible();
});

test('timed out request can be retried without leaving an endless spinner', async ({ page }) => {
  await page.clock.install();
  await page.route(`${api}/releases/latest`, () => {});
  await page.goto('/download');
  await expect(page.getByRole('status')).toContainText('正在读取');
  await page.clock.fastForward(16000);
  await expect(page.getByRole('alert')).toContainText('请求超时');
  await expect(page.getByRole('button', { name: '重试', exact: true })).toBeEnabled();
});

test('mobile navigation opens docs and a long asset name stays within the viewport', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/');
  await page.locator('.VPNavBarHamburger').click();
  await page.locator('.VPNavScreen').getByRole('link', { name: '使用文档', exact: true }).click();
  await expect(page).toHaveURL(/\/docs\/$/);
  const data = release(8);
  data.assets[0].name = 'a'.repeat(120) + '.deb';
  await page.route(`${api}/releases/latest`, (route) => route.fulfill({ json: data }));
  await page.goto('/download');
  await expect(page.locator('.asset-list a')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
});

test('static output excludes test reports and maintainer documents', async () => {
  const { existsSync, readdirSync } = await import('node:fs');
  const { resolve } = await import('node:path');
  const output = resolve('.vitepress/dist');
  for (const name of [
    'test-results',
    'playwright-report',
    'tests',
    'README.html',
    'RESEARCH.html',
  ]) {
    expect(existsSync(resolve(output, name)), name).toBe(false);
  }
  const html = readdirSync(output, { recursive: true }).filter((name) =>
    String(name).endsWith('.html'),
  );
  expect(html).toHaveLength(21);
});

test('all generated pages and sitemap use the sole production origin', async () => {
  const { readFileSync, readdirSync } = await import('node:fs');
  const { resolve } = await import('node:path');
  const output = resolve('.vitepress/dist');
  const origin = 'https://pixiu.arr2018.dpdns.org';
  for (const name of readdirSync(output, { recursive: true })) {
    if (!String(name).endsWith('.html')) continue;
    const html = readFileSync(resolve(output, String(name)), 'utf8');
    const canonical = html.match(/<link rel="canonical" href="([^"]+)"/);
    expect(canonical, String(name)).not.toBeNull();
    expect(new URL(canonical![1]).origin, String(name)).toBe(origin);
  }
  const sitemap = readFileSync(resolve(output, 'sitemap.xml'), 'utf8');
  const locations = [...sitemap.matchAll(/<loc>(.*?)<\/loc>/g)];
  expect(locations.length).toBeGreaterThan(0);
  for (const [, location] of locations) expect(new URL(location).origin).toBe(origin);
});
