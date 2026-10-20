import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { finalizeShots, flowSlug, REPO_ROOT, shot } from './evidence';

const page = { screenshot: async ({ path: p }: { path: string }) => fs.writeFileSync(p, 'png') };
const phase = `selftest-${process.pid}`;
const dir = path.join(REPO_ROOT, 'test-evidence', phase);
process.env.EVIDENCE_PHASE = phase;
delete process.env.EVIDENCE_DISABLED;

test('flowSlug kebab-cases top-level describe', () => {
  assert.equal(flowSlug(['a.spec.ts', 'Harness Smoke', 'x']), 'harness-smoke');
  assert.equal(flowSlug(['a.spec.ts', 'pytest-report', 'inner', 'x']), 'pytest-report');
});

test('promotes only on pass, exact path', async () => {
  try {
    const bad = { titlePath: ['f', 'my-flow', 't'], status: 'failed' };
    await shot(page, bad, 1, 'home');
    assert.deepEqual(finalizeShots(bad), []);
    assert.equal(fs.existsSync(dir), false);

    const good = { titlePath: ['f', 'my-flow', 't'], status: 'passed' };
    await shot(page, good, 1, 'home');
    await shot(page, good, 2, 'next');
    const out = finalizeShots(good);
    assert.equal(out[0], path.join(dir, 'my-flow', '01-home.png'));
    assert.ok(fs.existsSync(path.join(dir, 'my-flow', '02-next.png')));
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('throws without EVIDENCE_PHASE; disabled writes to outputDir only', async () => {
  const info = { titlePath: ['f', 'x', 't'], status: 'passed', outputDir: fs.mkdtempSync(path.join(os.tmpdir(), 'ev-')) };
  delete process.env.EVIDENCE_PHASE;
  await assert.rejects(shot(page, info, 1, 'a'), /EVIDENCE_PHASE/);
  process.env.EVIDENCE_DISABLED = '1';
  const out = await shot(page, info, 1, 'a');
  assert.equal(out, path.join(info.outputDir, '01-a.png'));
  assert.equal(fs.existsSync(path.join(REPO_ROOT, 'test-evidence', phase)), false);
});
