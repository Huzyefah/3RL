import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { REPO_ROOT, shot } from '../../support/evidence';
import { expect, test } from '../../support/test';

test.describe('pytest-report', () => {
  test('pytest HTML report screenshot', async ({ page }, testInfo) => {
    const rel = process.env.REPORT_HTML;
    test.skip(!rel, 'REPORT_HTML not set (e.g. test-evidence/phase-00-foundation/reports/pytest.html)');
    const file = path.resolve(REPO_ROOT, rel!);
    test.skip(!fs.existsSync(file), `report file not found: ${file}`);
    await page.goto(pathToFileURL(file).href);
    await expect(page.locator('body')).not.toBeEmpty();
    await shot(page, testInfo, 1, 'report');
  });
});
