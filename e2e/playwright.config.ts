import { defineConfig, devices } from "@playwright/test";

// @fake specs run against the local stack (`make dev`); @live specs need BASE_URL / API_URL of Cloud Run.
// MOCK=1 runs the UI against e2e/mock-api (port 8090) with its own Next dev server on 3100.
const mock = process.env.MOCK === "1";
const local = !process.env.BASE_URL;

const localServers = [
  { command: "make -C .. dev-api", url: "http://localhost:8080/healthz", reuseExistingServer: true, timeout: 120_000 },
  { command: "make -C .. dev-sim", url: "http://localhost:8081/healthz", reuseExistingServer: true, timeout: 120_000 },
  { command: "make -C .. dev-web", url: "http://localhost:3000", reuseExistingServer: true, timeout: 180_000 },
];

const mockServers = [
  { command: "node mock-api/server.mjs", url: "http://localhost:8090/healthz", reuseExistingServer: true, timeout: 30_000 },
  {
    command: "npm --prefix ../frontend run dev -- --port 3100",
    url: "http://localhost:3100",
    env: { SENTINEL_API_URL: "http://localhost:8090" },
    reuseExistingServer: true,
    timeout: 180_000,
  },
];

export default defineConfig({
  testDir: "./tests",
  outputDir: "./.results",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  reporter: [["list"], ["junit", { outputFile: "./.results/junit.xml" }]],
  use: {
    baseURL: process.env.BASE_URL ?? (mock ? "http://localhost:3100" : "http://localhost:3000"),
    ...devices["Desktop Chrome"],
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
  },
  webServer: mock ? mockServers : local ? localServers : undefined,
});
