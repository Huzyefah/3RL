import { expect, test } from "@playwright/test";
import { flowEvidence } from "../../utils/evidence";

// Runs against a real local stack: DEMO_URL=http://localhost:3100 (web → sentinel-api :8080, AUTOPLAY=0).
const BASE = process.env.DEMO_URL ?? "http://localhost:3100";

test("phase-06 demo control: replay BANK_C episode → real detector + agents → approve reroute @real", async ({ page }) => {
  test.setTimeout(240_000);
  const ev = flowEvidence("phase-06-frontend", "demo-control");
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${BASE}/demo`);
  await page.request.post(`${BASE}/api/demo/reset`);
  await expect(page.getByTestId("demo-episodes")).toBeVisible();
  await expect(page.getByTestId("episode-INC-PS02-0020")).toBeVisible();
  await ev.snap(page, "demo-tab");

  await page.getByTestId("replay-INC-PS02-0020").click();
  await expect(page.getByTestId("demo-msg")).toContainText("Replaying INC-PS02-0020");
  await ev.snap(page, "replay-started");

  await page.goto(`${BASE}/`);
  const row = page.locator('[data-testid^="incident-row-"]').first();
  await expect(row).toBeVisible({ timeout: 180_000 });
  await ev.snap(page, "live-ops-incident-detected");

  await row.locator("a").first().click();
  await expect(page.getByTestId("trace-timeline")).toBeVisible();
  await expect(page.getByText(/Challenge/).first()).toBeVisible({ timeout: 90_000 });
  const approve = page.locator('[data-testid^="approve-"]').first();
  await expect(approve).toBeVisible({ timeout: 90_000 });
  await ev.snap(page, "incident-agents-awaiting-approval");
  await approve.click();
  await expect(page.getByText(/Verified: the target metric recovered/)).toBeVisible({ timeout: 30_000 });
  await ev.snap(page, "approved-verified-resolved");
});
