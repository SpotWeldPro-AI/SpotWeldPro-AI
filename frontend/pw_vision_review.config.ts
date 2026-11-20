import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: "e2e_vision_review.spec.ts",
  timeout: 30_000,
  retries: 0,
  workers: 1,
  reporter: [["list"], ["json", { outputFile: "pw_vision_review_results.json" }]],
  use: {
    baseURL: "http://localhost:5173",
    headless: true,
    screenshot: "on",
    video: "off",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
