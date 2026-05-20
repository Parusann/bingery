import { test } from "@playwright/test";
import { pause, smoothScroll } from "./_helpers";

test("11 — Stats: Mio's rating + genre breakdown", async ({ page }) => {
  await page.goto("/stats");
  await page.waitForLoadState("networkidle").catch(() => {});
  await pause(page, 3500); // let charts animate in

  for (let i = 0; i < 4; i++) {
    await smoothScroll(page, 550, 1500);
  }
  await pause(page, 1200);

  await page.evaluate(() =>
    window.scrollTo({ top: 0, behavior: "smooth" })
  );
  await pause(page, 2000);
});
