import { expect, test, type Page } from "@playwright/test";
import { flowEvidence } from "../../utils/evidence";

// UI shell against e2e/mock-api. Run with `npm run test:mock` (MOCK=1). Skipped in the normal @fake suite.
const MOCK_API = "http://localhost:8090";
const INC = "INC-2026-1020-004";
const ACTION = "act-reroute-bank-c-01";
const SERVICES = [
  "PaymentGateway",
  "AuthService",
  "NotificationHub",
  "DataPipeline",
  "UserProfileService",
  "SearchAPI",
  "AnalyticsDashboard",
  "ReportGenerator",
];

// React streaming briefly parks resolved Suspense content in a hidden <div id="S:n"> outside the header; scope to the header.
const header = (page: Page) => page.getByRole("banner");

const seconds = async (page: Page, scope = page.getByTestId(`incident-row-${INC}`)) =>
  Number(await scope.getByTestId("eta-countdown").getAttribute("data-seconds"));

test.describe("phase-02 UI shell on mock SSE @fake", () => {
  test.skip(process.env.MOCK !== "1", "needs MOCK=1 (mock-api on :8090, web on :3100)");

  test("Live Ops, live incident with ticking ETA, incident trace with plan v2, mobile layout", async ({ page, request }) => {
    const ev = flowEvidence("phase-02-generator-sim-ui", "ui-shell-mock");
    const reset = await request.post(`${MOCK_API}/mock/reset`);
    expect(reset.ok()).toBeTruthy();

    // ── Live Ops (desktop) ──
    await page.goto("/");
    await expect(header(page).getByTestId("api-status")).toBeVisible();
    await expect(header(page).getByTestId("api-status")).toContainText("OK");
    await expect(header(page).getByTestId("csv-rows")).toHaveText("500");
    await expect(page.getByTestId("synthetic-badge")).toBeVisible();
    await expect(page.getByTestId("stream-status")).toHaveAttribute("data-state", "live");
    await expect(page.getByTestId("autonomy-chip")).toBeVisible();
    await expect(page.getByTestId("autonomy-chip")).toContainText(/shadow/i);
    await expect(page.getByTestId("kpi-strip")).toBeVisible();
    for (const svc of SERVICES) {
      const card = page.getByTestId(`service-card-${svc}`);
      await expect(card).toBeVisible();
      await expect(card.getByTestId(`service-band-${svc}`)).toBeVisible();
      await expect(card.getByTestId(`service-band-${svc}`)).toHaveText(/Normal|Warning|Critical/);
    }
    await expect(page.getByTestId("bank-strip")).toBeVisible();
    for (const b of ["BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E"]) {
      await expect(page.getByTestId(`bank-${b}`)).toBeVisible();
      await expect(page.getByTestId(`bank-rail-${b}`)).toHaveText("IBFT");
    }
    await ev.snap(page, "live-ops-desktop");

    // ── Incident appears via SSE, BANK_C turns amber, countdown ticks down ──
    const row = page.getByTestId(`incident-row-${INC}`);
    await expect(row).toBeVisible({ timeout: 15_000 });
    await expect(row).toContainText("BANK_C");
    await expect(row.getByTestId("severity-chip")).toHaveText("P1");
    await expect(row.getByTestId("incident-root")).toHaveText("PaymentGateway");
    await expect(row.getByTestId("incident-pkr")).toContainText("1.25M");
    await expect(row.getByTestId("incident-pkr")).toContainText("est.");
    const eta = row.getByTestId("eta-countdown");
    await expect(eta).toBeVisible();
    await expect(eta).toHaveText(/^1[01]:\d\d$/);
    const first = await seconds(page);
    await expect.poll(() => seconds(page), { timeout: 5_000 }).toBeLessThan(first);
    expect(first).toBeGreaterThan(600);

    await expect(page.getByTestId("bank-band-BANK_C")).toHaveText("Warning", { timeout: 15_000 });
    await expect(page.getByTestId("bank-band-BANK_A")).toHaveText("Normal");

    // HITL reroute lands in the inline approvals inbox once the guard step streams in.
    const inbox = page.getByTestId("approvals-inbox");
    await expect(inbox.getByTestId(`approve-${ACTION}`)).toBeVisible({ timeout: 15_000 });
    await expect(inbox.getByTestId(`reject-${ACTION}`)).toBeVisible();
    await expect(inbox).toContainText("Reroute BANK_C IBFT → RAAST");
    await ev.snap(page, "live-ops-incident-countdown");

    // ── Incident page ──
    await row.getByTestId("incident-link").click();
    await expect(page).toHaveURL(new RegExp(`/incidents/${INC}$`));
    await expect(page.getByTestId("incident-headline")).toBeVisible();
    await expect(page.getByTestId("goal-banner")).toContainText("Prevent BANK_C payment failures");
    await expect(page.getByTestId("incident-banner").getByTestId("eta-countdown")).toBeVisible();

    const trace = page.getByTestId("trace-timeline");
    await expect(trace).toBeVisible();
    // Full sequence goal → plan v1 → tool calls → challenge (DISPUTED) → plan v2 → guard → verify.
    await expect(page.getByTestId("trace-step-11")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("trace-kind-1")).toHaveText("Goal");
    await expect(page.getByTestId("trace-kind-2")).toHaveText("Plan v1");
    await expect(page.getByTestId("trace-kind-3")).toHaveText("Tool call");
    await expect(page.getByTestId("trace-kind-5")).toHaveText("Challenge · DISPUTED");
    await expect(page.getByTestId("trace-kind-6")).toBeVisible();
    await expect(page.getByTestId("trace-kind-6")).toHaveText("Plan v2");
    await expect(page.getByTestId("trace-step-6")).toContainText("Skeptic disputed");
    await expect(page.getByTestId("trace-kind-8")).toHaveText("Challenge · CONFIRMED");
    await expect(page.getByTestId("trace-kind-10")).toHaveText("Guard · HITL");
    await expect(page.getByTestId("trace-kind-11")).toHaveText("Verify");

    await expect(page.getByTestId("hypothesis-0")).toBeVisible();
    await expect(page.getByTestId("hypothesis-0")).toContainText("RC-BANK");
    await expect(page.getByTestId("skeptic-verdict")).toBeVisible();
    await expect(page.getByTestId("skeptic-verdict")).toContainText("CONFIRMED");
    await expect(page.getByTestId("similar-incidents")).toContainText("INC-0007");
    await expect(page.getByTestId("comms-draft")).toBeVisible();
    await expect(page.getByTestId("incident-actions").getByTestId(`approve-${ACTION}`)).toBeVisible();
    await expect(page.getByTestId("feedback-up")).toBeVisible();
    await ev.snap(page, "incident-trace-plan-v2");

    // Evidence chip opens the evidence inspector popover.
    await page.getByTestId("hypothesis-0").getByTestId("evidence-segment:3fa1c2d9").click();
    const pop = page.getByTestId("evidence-popover").filter({ visible: true });
    await expect(pop).toBeVisible();
    await expect(pop).toContainText("segment:3fa1c2d9");
    await ev.snap(page, "incident-evidence-popover", false);
    await page.keyboard.press("Escape");
    await expect(pop).toBeHidden();

    // ── Technical / business toggle ──
    const summary = page.getByTestId("summary-text");
    await expect(summary).toBeVisible();
    await expect(summary).toHaveAttribute("data-mode", "technical");
    await expect(summary).toContainText("RC=91");
    await page.getByTestId("summary-toggle-business").click();
    await expect(summary).toHaveAttribute("data-mode", "business");
    await expect(summary).toBeVisible();
    await expect(summary).toContainText("4,100 customers");
    await expect(summary).not.toContainText("RC=91");
    await page.getByTestId("summary-panel").scrollIntoViewIfNeeded();
    await ev.snap(page, "incident-business-summary", false);

    // ── Mobile 390×844 ──
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    await expect(page.getByTestId(`incident-row-${INC}`)).toBeVisible();
    await expect(page.getByTestId("kpi-strip")).toBeVisible();
    await expect(page.getByTestId("bank-BANK_C")).toBeVisible();
    await expect(header(page).getByTestId("api-status")).toBeVisible();
    const sw = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(sw).toBeLessThanOrEqual(390);
    await ev.snap(page, "live-ops-mobile");

    await page.goto(`/incidents/${INC}`);
    await expect(page.getByTestId("trace-step-6")).toBeVisible();
    const swInc = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(swInc).toBeLessThanOrEqual(390);
    await ev.snap(page, "incident-mobile");

    // ── Dark mode (prefers-color-scheme) ──
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/");
    await expect(page.getByTestId(`incident-row-${INC}`)).toBeVisible();
    await expect(page.getByTestId("bank-band-BANK_C")).toHaveText("Warning");
    await expect(header(page).getByTestId("api-status")).toContainText("OK");
    await page.waitForTimeout(400); // let the 220 ms row entry animation settle before the screenshot
    await ev.snap(page, "live-ops-dark");
  });
});
