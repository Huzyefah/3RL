import { defineConfig, devices } from "@playwright/test";

// @fake specs run against the local stack (`make dev`); @live specs need BASE_URL / API_URL of Cloud Run.
const local = !process.env.BASE_URL;

export default defineConfig({
  testDir: "./tests",
  outputDir: "./.results",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  reporter: [["list"], ["junit", { outputFile: "./.results/junit.xml" }]],
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:3000",
    ...devices["Desktop Chrome"],
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
  },
  webServer: local
    ? [
        { command: "make -C .. dev-api", url: "http://localhost:8080/health", reuseExistingServer: true, timeout: 120_000 },
        { command: "make -C .. dev-sim", url: "http://localhost:8081/health", reuseExistingServer: true, timeout: 120_000 },
        { command: "make -C .. dev-web", url: "http://localhost:3000", reuseExistingServer: true, timeout: 180_000 },
      ]
    : undefined,
});
