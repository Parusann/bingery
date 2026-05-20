import { test } from "@playwright/test";
import { pause, smoothScroll } from "./_helpers";

test("12 — Activity feed", async ({ page }) => {
  await page.goto("/activity");
  await page.waitForLoadState("networkidle").catch(() => {});
  await pause(page, 2500);

  for (let i = 0; i < 3; i++) {
    await smoothScroll(page, 550, 1500);
  }
  await pause(page, 1500);
});
