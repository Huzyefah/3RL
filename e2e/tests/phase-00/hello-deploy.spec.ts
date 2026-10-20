import { expect, test } from "@playwright/test";
import { flowEvidence, showJson } from "../../utils/evidence";

// Run with BASE_URL=https://sentinel-web-725314964496.us-central1.run.app
const PNUM = "725314964496";
const API = `https://sentinel-api-${PNUM}.us-central1.run.app`;
const SIM = `https://finpay-sim-${PNUM}.us-central1.run.app`;

test("phase-00 hello deploy on Cloud Run @live", async ({ page, request }) => {
  test.skip(!process.env.BASE_URL, "BASE_URL not set");
  const ev = flowEvidence("phase-00-bootstrap", "hello-deploy");

  // Web is public and reaches the PRIVATE api through its proxy (ID token, server-side).
  const proxied = await request.get("/api/health");
  expect(proxied.status()).toBe(200);
  const body = await proxied.json();
  expect(body).toMatchObject({ status: "ok", service: "sentinel-api", env: "prod", csv_rows: 500 });
  await showJson(page, "sentinel-web → /api/health → sentinel-api (Cloud Run, private)", body);
  await ev.snap(page, "web-proxy-to-private-api");

  // Direct unauthenticated calls to the private services are rejected by Cloud Run IAM.
  const apiDirect = await request.get(`${API}/health`);
  const simDirect = await request.get(`${SIM}/health`);
  expect(apiDirect.status()).toBe(403);
  expect(simDirect.status()).toBe(403);
  await showJson(page, "Unauthenticated direct calls (expected 403)", {
    [`${API}/health`]: apiDirect.status(),
    [`${SIM}/health`]: simDirect.status(),
  });
  await ev.snap(page, "private-services-403");

  await page.goto("/");
  await expect(page.getByTestId("api-status")).toBeVisible();
  await expect(page.getByTestId("api-status")).toContainText("OK");
  await expect(page.getByTestId("csv-rows")).toHaveText("500");
  await ev.snap(page, "web-home-live");
});
