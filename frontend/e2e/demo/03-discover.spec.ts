import { test, expect } from "@playwright/test";
import { pause, smoothScroll, typeSlowly } from "./_helpers";

test("03 — Discover: browse grid, search, and filter", async ({ page }) => {
  await page.goto("/discover");
  await expect(
    page.getByRole("heading", { name: "Discover", exact: true })
  ).toBeVisible();
  await pause(page, 2200);

  // Scroll through several rows of the grid
  await smoothScroll(page, 700, 1500);
  await smoothScroll(page, 700, 1500);
  await smoothScroll(page, 700, 1500);
  await pause(page, 800);

  // Back to top, then perform a search
  await page.evaluate(() =>
    window.scrollTo({ top: 0, behavior: "smooth" })
  );
  await pause(page, 1500);

  const search = page
    .locator('input[type="search"], input[placeholder*="Search" i]')
    .first();
  if (await search.count()) {
    await search.click();
    await typeSlowly(page, 'input[type="search"], input[placeholder*="Search" i]', "Steins;Gate");
    await pause(page, 2200);
    await page.keyboard.press("Enter");
    await pause(page, 2500);
  } else {
    // Fallback — drive via URL
    await page.goto("/discover?q=Steins%3BGate");
    await pause(page, 2500);
  }
});
