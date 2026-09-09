import { test, expect } from '@playwright/test';

test('homepage entry and reversible selection enforce one to three finalists', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('link', { name: '配音试听', exact: true }).click();
  await expect(page).toHaveURL(/voice-audition\.html$/);
  const next = page.locator('#next');
  await expect(next).toBeDisabled();
  const checks = page.getByRole('checkbox');
  await expect(checks).toHaveCount(12);
  for (let i = 0; i < 5; i++) await checks.nth(i).check();
  await next.click();
  await expect(page.locator('.voice-card')).toHaveCount(5);
  await expect(next).toBeDisabled();
  const toggle = page.locator('.toggle');
  await toggle.nth(0).click();
  await expect(next).toBeDisabled();
  await toggle.nth(1).click();
  await expect(next).toBeEnabled();
  await expect(page.locator('.removed')).toHaveCount(2);
  await toggle.nth(1).click();
  await expect(next).toBeDisabled();
  await toggle.nth(1).click();
  const writes: string[] = [];
  page.on('request', (r) => {
    if (r.method() !== 'GET') writes.push(r.url());
  });
  await next.click();
  await expect(page.locator('#result-list li')).toHaveCount(3);
  await expect(page.locator('#cards')).toBeHidden();
  await page.locator('#back').click();
  for (let i = 2; i < 5; i++) await toggle.nth(i).click();
  await expect(next).toBeDisabled();
  await toggle.nth(0).click();
  await next.click();
  await expect(page.locator('#result-list li')).toHaveCount(1);
  expect(writes).toEqual([]);
  await page.reload();
  await expect(page.getByRole('checkbox', { checked: true })).toHaveCount(0);
});

test('all audio assets load and mobile results fit', async ({ page, request }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/voice-audition.html');
  const paths = await page
    .locator('audio')
    .evaluateAll((nodes) => nodes.map((node) => node.getAttribute('src')!));
  expect(new Set(paths).size).toBe(12);
  for (const path of paths) {
    const response = await request.get(path);
    expect(response.ok(), path).toBeTruthy();
    expect(response.headers()['content-type']).toContain('audio/mpeg');
    expect((await response.body()).length).toBeGreaterThan(100_000);
  }
  await page
    .locator('audio')
    .first()
    .evaluate(async (node: HTMLAudioElement) => {
      await node.play();
    });
  await expect
    .poll(() =>
      page
        .locator('audio')
        .first()
        .evaluate((node: HTMLAudioElement) => node.currentTime),
    )
    .toBeGreaterThan(0);
  for (let i = 0; i < 3; i++) await page.getByRole('checkbox').nth(i).check();
  await page.locator('#next').click();
  await page.locator('#next').click();
  await expect(page.locator('#result-list li')).toHaveCount(3);
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBeTruthy();
  await page.screenshot({ path: 'test-results/voice-choice-mobile.png', fullPage: true });
});
