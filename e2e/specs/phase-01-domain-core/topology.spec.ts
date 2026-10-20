import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { REPO_ROOT, shot } from '../../support/evidence';
import { expect, test } from '../../support/test';

// The plot comes from `uv run python scripts/plot_topology.py` (dataviz output, not a UI screenshot).
test.describe('topology-graph', () => {
  test('service dependency graph with owners and segments', async ({ page }, testInfo) => {
    const file = path.resolve(REPO_ROOT, 'backend/.cache/plots/topology.png');
    test.skip(!fs.existsSync(file), 'run scripts/plot_topology.py first');
    await page.goto(pathToFileURL(file).href);
    await expect(page.locator('img')).toBeVisible();
    await shot(page, testInfo, 1, 'topology');
  });
});
