import AxeBuilder from '@axe-core/playwright';
import type { Page } from '@playwright/test';

/** Fails on serious/critical axe violations. */
export async function checkA11y(page: Page): Promise<void> {
  const { violations } = await new AxeBuilder({ page }).analyze();
  const bad = violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
  if (bad.length > 0) {
    const msg = bad.map((v) => `${v.impact} ${v.id}: ${v.help} (${v.nodes.length} nodes)`).join('\n');
    throw new Error(`Accessibility violations:\n${msg}`);
  }
}
