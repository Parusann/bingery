import { test, expect } from "@playwright/test";
import { pause, smoothScroll, typeSlowly } from "./_helpers";

// The Compare page now compares two ANIME (not two users). The flow:
// type into Anime A picker → pick a result → type into Anime B picker →
// pick a result → backend returns side-by-side cards with shared/unique
// genres, scores, studios, and the user's own ratings.
test("13 — Compare two anime side-by-side", async ({ page }) => {
  test.setTimeout(60_000);
  await page.goto("/compare");
  await expect(
    page.getByRole("heading", { name: "Compare anime", exact: true })
  ).toBeVisible();
  await pause(page, 2200);

  // Pick anime A — search "Steins;Gate"
  const inputA = page
    .locator('input[placeholder="Search anime…"]')
    .first();
  await inputA.click();
  await typeSlowly(page, 'input[placeholder="Search anime…"]', "Steins;Gate");
  await pause(page, 1800);
  // First dropdown match
  await page.locator('button:has(img[alt=""])').first().click();
  await pause(page, 1500);

  // Pick anime B — search "Erased"
  // After A is picked, the remaining picker's input is now the first visible
  // input[placeholder="Search anime…"] on the page.
  const inputB = page
    .locator('input[placeholder="Search anime…"]')
    .first();
  await inputB.click();
  await typeSlowly(page, 'input[placeholder="Search anime…"]', "Erased");
  await pause(page, 1800);
  await page.locator('button:has(img[alt=""])').first().click();

  // Wait for the side-by-side cards to render — the Overlap heading is the
  // canonical sentinel that the comparison loaded.
  await expect(
    page.getByRole("heading", { name: "Overlap" })
  ).toBeVisible({ timeout: 15_000 });
  await pause(page, 3000);

  // Scroll through the comparison so genres + overlap callout are visible
  await smoothScroll(page, 400, 1400);
  await smoothScroll(page, 400, 1400);
  await pause(page, 1500);

  await page.evaluate(() =>
    window.scrollTo({ top: 0, behavior: "smooth" })
  );
  await pause(page, 1800);
});
