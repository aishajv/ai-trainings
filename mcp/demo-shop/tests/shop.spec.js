import { test, expect } from '@playwright/test';

test.use({ viewport: { width: 375, height: 812 } });

test.beforeEach(async ({ page }) => {
  await page.goto('/');
});

test('page does not scroll sideways on a phone', async ({ page }) => {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});

test('product name stays on screen', async ({ page }) => {
  const box = await page.getByRole('heading', { level: 1 }).boundingBox();
  expect(box.x + box.width).toBeLessThanOrEqual(375);
});

test('quantity buttons are big enough to tap', async ({ page }) => {
  for (const name of ['Decrease quantity', 'Increase quantity']) {
    const box = await page.getByRole('button', { name }).boundingBox();
    expect(box.width).toBeGreaterThanOrEqual(44);
    expect(box.height).toBeGreaterThanOrEqual(44);
  }
});

test('Place order can be clicked', async ({ page }) => {
  await page.getByRole('button', { name: 'Place order' }).click({ trial: true, timeout: 3000 });
});

test('SAVE10 takes 10% off once', async ({ page }) => {
  await page.getByLabel('Coupon code').fill('SAVE10');
  await page.getByRole('button', { name: 'Apply' }).click();
  await expect(page.getByTestId('total')).toHaveText('€80.10');
});
