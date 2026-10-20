import { checkA11y } from '../../support/axe';
import { shot } from '../../support/evidence';
import { expect, test } from '../../support/test';

test.describe('harness-smoke', () => {
  test('home page renders and is accessible', async ({ page }, testInfo) => {
    await page.goto('/');
    await expect(page.getByText('Sentinel').first()).toBeVisible();
    await shot(page, testInfo, 1, 'home');
    await checkA11y(page);
  });
});
