import fs from 'node:fs';
import path from 'node:path';
import { REPO_ROOT, shot } from '../../support/evidence';
import { expect, test } from '../../support/test';

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

test.describe('eda-facts', () => {
  test('rule baselines table', async ({ page }, testInfo) => {
    const csv = path.join(REPO_ROOT, 'analysis', 'outputs', 'rule_baselines.csv');
    test.skip(!fs.existsSync(csv), `CSV not found: ${csv}`);
    const rows = fs
      .readFileSync(csv, 'utf8')
      .trim()
      .split(/\r?\n/)
      .map((l) => l.split(','));
    const [head, ...body] = rows;
    const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>rule_baselines</title>
<style>body{font:14px sans-serif;margin:16px}table{border-collapse:collapse}td,th{border:1px solid #888;padding:4px 8px}th{background:#eee}</style></head>
<body><h1>rule_baselines.csv</h1><table><thead><tr>${head.map((h) => `<th>${esc(h)}</th>`).join('')}</tr></thead>
<tbody>${body.map((r) => `<tr>${r.map((c) => `<td>${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></body></html>`;
    await page.setContent(html);
    await expect(page.locator('table')).toBeVisible();
    await shot(page, testInfo, 1, 'rule-baselines');
  });
});
