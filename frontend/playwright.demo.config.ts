import { defineConfig, devices } from "@playwright/test";

// Separate config dedicated to producing demo videos.
// Run with:  npx playwright test --config=playwright.demo.config.ts
// Outputs videos under ../demo-captures/raw/<test-id>/video.webm

export default defineConfig({
  testDir: "./e2e/demo",
  outputDir: "../demo-captures/raw",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:5173",
    viewport: { width: 1920, height: 1080 },
    video: {
      mode: "on",
      size: { width: 1920, height: 1080 },
    },
    trace: "off",
    screenshot: "off",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: true,
    timeout: 60_000,
  },
  projects: [
    {
      name: "setup",
      testMatch: /auth\.setup\.ts$/,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "logged-out",
      testMatch: /(01-landing|02-auth)\.spec\.ts$/,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "logged-in",
      testMatch: /(03|04|05|06|07|08|09|10|11|12|13|14)-.*\.spec\.ts$/,
      dependencies: ["setup"],
      use: {
        ...devices["Desktop Chrome"],
        storageState: "e2e/demo/.auth/demo.json",
      },
    },
  ],
});
