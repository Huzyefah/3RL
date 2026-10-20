import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

/** Repo root, resolved from this file so it works from any cwd (e2e/support -> repo). */
export const REPO_ROOT = path.resolve(__dirname, '..', '..');

type ShotPage = { screenshot(options: { path: string; fullPage?: boolean }): Promise<unknown> };
export type ShotInfo = {
  titlePath: string[];
  status?: string;
  outputDir?: string;
  testId?: string;
};

type Pending = { tmp: string; dest: string };
const pending = new Map<string, Pending[]>();
const tmpDirs = new Map<string, string>();

export const pad2 = (n: number): string => String(n).padStart(2, '0');

export function kebab(s: string): string {
  return s
    .replace(/([a-z0-9])([A-Z])/g, '$1-$2')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

/** titlePath is [file, describe..., test]; flow = top-level describe (falls back to file basename). */
export function flowSlug(titlePath: string[]): string {
  const name = titlePath.length >= 3 ? titlePath[1] : path.basename(titlePath[0] ?? 'flow').replace(/\.spec\.\w+$/, '');
  return kebab(name);
}

function key(info: ShotInfo): string {
  return info.testId ?? info.titlePath.join(' > ');
}

function evidenceEnabled(): boolean {
  return process.env.EVIDENCE_DISABLED !== '1';
}

export async function shot(page: ShotPage, info: ShotInfo, idx: number, step: string): Promise<string> {
  const file = `${pad2(idx)}-${step}.png`;
  const k = key(info);
  if (!evidenceEnabled()) {
    const dir = info.outputDir ?? path.join(REPO_ROOT, 'e2e', 'test-results');
    fs.mkdirSync(dir, { recursive: true });
    const out = path.join(dir, file);
    await page.screenshot({ path: out });
    return out;
  }
  const phase = process.env.EVIDENCE_PHASE;
  if (!phase) {
    throw new Error('EVIDENCE_PHASE is not set (e.g. phase-00-foundation). Set EVIDENCE_DISABLED=1 to skip evidence.');
  }
  let tmpDir = tmpDirs.get(k);
  if (!tmpDir) {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sentinel-shots-'));
    tmpDirs.set(k, tmpDir);
  }
  const tmp = path.join(tmpDir, file);
  const dest = path.join(REPO_ROOT, 'test-evidence', phase, flowSlug(info.titlePath), file);
  await page.screenshot({ path: tmp });
  const list = pending.get(k) ?? [];
  list.push({ tmp, dest });
  pending.set(k, list);
  return dest;
}

/** Called after each attempt: promote temp shots only if the attempt passed; always clean up. */
export function finalizeShots(info: ShotInfo): string[] {
  const k = key(info);
  const promoted: string[] = [];
  if (info.status === 'passed') {
    for (const { tmp, dest } of pending.get(k) ?? []) {
      fs.mkdirSync(path.dirname(dest), { recursive: true });
      fs.copyFileSync(tmp, dest);
      promoted.push(dest);
    }
  }
  const dir = tmpDirs.get(k);
  if (dir) fs.rmSync(dir, { recursive: true, force: true });
  pending.delete(k);
  tmpDirs.delete(k);
  return promoted;
}
