import fs from "node:fs";
import path from "node:path";
import type { Page } from "@playwright/test";

// Evidence lives at docs/test-evidence/<phase>/<flow>/<NN>-<step>.png (see root CLAUDE.md).
const ROOT = path.resolve(__dirname, "../../docs/test-evidence");

export function evidenceDir(phase: string, flow: string): string {
  const dir = path.join(ROOT, phase, flow);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

export function flowEvidence(phase: string, flow: string) {
  const dir = evidenceDir(phase, flow);
  let n = 0;
  return {
    dir,
    async snap(page: Page, step: string, fullPage = true) {
      n += 1;
      const file = path.join(dir, `${String(n).padStart(2, "0")}-${step}.png`);
      await page.screenshot({ path: file, fullPage });
      return file;
    },
    write(name: string, content: string) {
      fs.writeFileSync(path.join(dir, name), content);
    },
  };
}

// Renders a JSON body as a readable page so API responses can be screenshotted as evidence.
export async function showJson(page: Page, title: string, body: unknown) {
  const esc = (s: string) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]!);
  await page.setContent(
    `<html><body style="font:14px ui-monospace,monospace;padding:24px;background:#0b0d10;color:#e6e6e6">
     <h2 style="font-family:system-ui">${esc(title)}</h2><pre>${esc(JSON.stringify(body, null, 2))}</pre></body></html>`,
  );
}
