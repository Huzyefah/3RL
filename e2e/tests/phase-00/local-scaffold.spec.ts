import { expect, test } from "@playwright/test";
import { flowEvidence, showJson } from "../../utils/evidence";

test("phase-00 local scaffold: web renders and reaches api via proxy @fake", async ({ page, request }) => {
  const ev = flowEvidence("phase-00-bootstrap", "local-scaffold");

  const api = await request.get("http://localhost:8080/healthz");
  expect(api.ok()).toBeTruthy();
  const body = await api.json();
  expect(body.csv_rows).toBe(500);
  await showJson(page, "sentinel-api GET /healthz (local)", body);
  await ev.snap(page, "api-healthz");

  const proxied = await request.get("/api/healthz");
  expect((await proxied.json()).status).toBe("ok");
  await showJson(page, "sentinel-web GET /api/healthz (same-origin proxy)", await proxied.json());
  await ev.snap(page, "web-proxy-healthz");

  await page.goto("/");
  await expect(page.getByTestId("api-status")).toBeVisible();
  await expect(page.getByTestId("api-status")).toContainText("OK");
  await expect(page.getByText("Checking API…")).toBeHidden();
  await expect(page.getByTestId("csv-rows")).toHaveText("500");
  await ev.snap(page, "web-home");
});
