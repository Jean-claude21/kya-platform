import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light', reducedMotion: 'reduce' });
});

test('critical system journey remains semantic and keyboard reachable', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('navigation', { name: 'Navigation principale' })).toBeVisible();
  const systems = page.getByRole('button', { name: /Systèmes/ });
  await systems.focus();
  await expect(systems).toBeFocused();
  await systems.press('Enter');

  await expect(
    page.getByRole('heading', { level: 1, name: 'Où se trouve la donnée qui fait foi ?' }),
  ).toBeVisible();
  await expect(page.getByRole('table', { name: 'Autorités de données' })).toBeVisible();
  await expect(page.getByText('KYA Platform', { exact: true }).first()).toBeVisible();
});

test('mobile layout does not create page-level horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto('/');
  await page.getByRole('button', { name: /Systèmes/ }).click();

  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));

  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth + 1);
  await expect(
    page.getByRole('heading', { name: 'Où se trouve la donnée qui fait foi ?' }),
  ).toBeVisible();
});

test('primary content appears when static resources are delayed', async ({ page }) => {
  await page.route('**/*', async (route) => {
    if (route.request().resourceType() !== 'document') {
      await new Promise((resolve) => setTimeout(resolve, 200));
    }
    await route.continue();
  });

  await page.goto('/');

  await expect(page.getByRole('main')).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
});
