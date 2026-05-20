import { test } from "@playwright/test";
import { pause, smoothScroll } from "./_helpers";

test("09 — Collections: list of Mio's lists, click into one", async ({
  page,
}) => {
  await page.goto("/collections");
  await page.waitForLoadState("networkidle").catch(() => {});
  await pause(page, 3000);

  // Scroll through the grid of collection cards
  await smoothScroll(page, 500, 1500);
  await pause(page, 800);
  await page.evaluate(() =>
    window.scrollTo({ top: 0, behavior: "smooth" })
  );
  await pause(page, 1500);

  // Click into the first collection card
  const link = page.locator('a[href^="/collections/"]').first();
  if (await link.count()) {
    await link.click();
    await page.waitForURL(/\/collections\/\d+/, { timeout: 15_000 }).catch(() => {});
    await pause(page, 2500);
    for (let i = 0; i < 3; i++) {
      await smoothScroll(page, 600, 1500);
    }
    await pause(page, 1500);
  } else {
    await pause(page, 2000);
  }
});
