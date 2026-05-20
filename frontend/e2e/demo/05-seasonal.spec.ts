import { test, expect } from "@playwright/test";
import { pause, smoothScroll } from "./_helpers";

test("05 — Seasonal: season picker + grid", async ({ page }) => {
  await page.goto("/seasonal");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await pause(page, 2500);

  // Scroll through the seasonal grid
  await smoothScroll(page, 600, 1400);
  await smoothScroll(page, 600, 1400);
  await pause(page, 800);

  await page.evaluate(() =>
    window.scrollTo({ top: 0, behavior: "smooth" })
  );
  await pause(page, 1500);

  // Try to open the season picker and pick a different season
  const pickerButtons = page.locator(
    'button:has-text("winter"), button:has-text("spring"), button:has-text("summer"), button:has-text("fall")'
  );
  if (await pickerButtons.count()) {
    await pickerButtons.first().click({ trial: false }).catch(() => {});
    await pause(page, 1800);
  } else {
    // Fallback: select tag if present
    const selects = page.locator("select");
    if (await selects.count()) {
      await selects.first().selectOption({ index: 1 }).catch(() => {});
      await pause(page, 1800);
    }
  }

  await pause(page, 2000);
});
