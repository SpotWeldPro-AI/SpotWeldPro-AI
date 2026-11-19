import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: "e2e_real_03_review.spec.ts",
  timeout: 45_000,
  retries: 0,
  workers: 1,
  reporter: [["list"], ["json", { outputFile: "pw_real03_results.json" }]],
  use: {
    baseURL: "http://localhost:5175",
    headless: true,
    screenshot: "on",
    video: "off",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
