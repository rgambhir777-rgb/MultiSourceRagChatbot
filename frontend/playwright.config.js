// End-to-end (E2E) tests: a real browser drives the real app (UI + API + databases + OpenAI).
//
//   npm run e2e            run all E2E tests (needs `docker compose up -d` and the API running)
//   npm run e2e:report     open the HTML report
//
// Tests run one at a time: they share one backend and make real (paid, but tiny) OpenAI calls.
import { defineConfig, devices } from "@playwright/test";

export const RESULTS_DIR = "e2e-results";

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.js",
  globalTeardown: "./e2e/global-teardown.js",
  timeout: 150_000, // a whole test, incl. waiting for real answers
  expect: { timeout: 15_000 },
  workers: 1,
  fullyParallel: false,
  retries: 0,
  reporter: [
    ["list"],
    ["html", { outputFolder: `${RESULTS_DIR}/report`, open: "never" }],
    ["json", { outputFile: `${RESULTS_DIR}/results.json` }],
  ],
  outputDir: `${RESULTS_DIR}/artifacts`,
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure", // a step-by-step recording when a test fails
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1360, height: 860 } },
    },
  ],
  // Start the Vite dev server if it isn't running already.
  webServer: {
    command: "npm run dev -- --host 127.0.0.1",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
