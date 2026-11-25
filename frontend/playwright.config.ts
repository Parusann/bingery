import { defineConfig } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { tmpdir } from "node:os";
import path from "node:path";

const port = process.env.BINGERY_E2E_PORT || "5187";
const baseURL = `http://127.0.0.1:${port}`;
process.env.BINGERY_E2E_MAIL ??= path.join(tmpdir(), `bingery-mail-${randomUUID()}.log`);

export default defineConfig({
  testDir: "./e2e",
  testIgnore: "**/demo/**",
  workers: 1,
  timeout: 45_000,
  use: { baseURL, trace: "retain-on-failure", serviceWorkers: "block" },
  webServer: {
    command: "python e2e/server.py",
    url: baseURL + "/api/health",
    env: { BINGERY_E2E_PORT: port, BINGERY_E2E_MAIL: process.env.BINGERY_E2E_MAIL },
    reuseExistingServer: false,
  },
});
