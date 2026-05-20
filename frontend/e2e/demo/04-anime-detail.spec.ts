import { test, expect } from "@playwright/test";
import { pause, smoothScroll } from "./_helpers";

test("04 — Anime detail page: click into a title and scroll", async ({
  page,
}) => {
  await page.goto("/discover");
  await expect(
    page.getByRole("heading", { name: "Discover", exact: true })
  ).toBeVisible();
  await pause(page, 1500);

  // Click the first anime card link
  const firstLink = page.locator('a[href^="/anime/"]').first();
  await firstLink.waitFor({ state: "visible" });
  await firstLink.click();
  await page.waitForURL(/\/anime\/\d+/);
  await pause(page, 2200);

  // Slow scroll through the detail page
  for (let i = 0; i < 5; i++) {
    await smoothScroll(page, 600, 1400);
  }
  await pause(page, 1500);

  // Scroll back to the hero
  await page.evaluate(() =>
    window.scrollTo({ top: 0, behavior: "smooth" })
  );
  await pause(page, 1800);
});
