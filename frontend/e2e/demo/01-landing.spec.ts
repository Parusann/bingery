import { test, expect } from "@playwright/test";
import { pause } from "./_helpers";

test("01 — Landing film spotlight, catalog, and watchlist tools", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Discover what/i })).toBeVisible();
  await pause(page, 1200);
  await page.getByRole("button", { name: "Next spotlight film" }).click();
  await expect(page.getByRole("link", { name: "Princess Mononoke", exact: true }).first()).toBeVisible();
  await pause(page, 1200);
  for (const name of ["Top rated anime", "Plan your next watch"]) {
    await page.getByRole("heading", { name }).scrollIntoViewIfNeeded();
    await pause(page, 1200);
  }
  await expect(page.getByRole("link", { name: "Join the waitlist" })).toHaveAttribute("href", "/auth?mode=waitlist");
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  await pause(page, 1200);
});
