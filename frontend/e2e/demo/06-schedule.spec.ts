import { test, expect } from "@playwright/test";
import { pause, smoothScroll } from "./_helpers";

test("06 — Schedule: weekly day-board with filters", async ({ page }) => {
  await page.goto("/schedule");

  await expect(
    page.getByRole("heading", { name: /airing/i })
  ).toBeVisible({ timeout: 15_000 });

  // 7 day sections render
  await expect(page.locator('section[id^="day-"]')).toHaveCount(7);
  await pause(page, 2500);

  // Scroll through the week
  await smoothScroll(page, 500, 1300);
  await pause(page, 800);

  // Toggle through SUB / DUB / BOTH via FilterPills
  for (const label of ["DUB", "BOTH", "SUB"] as const) {
    const btn = page.getByRole("button", { name: label, exact: true }).first();
    if (await btn.count()) {
      await btn.click().catch(() => {});
      await pause(page, 2200);
    }
  }

  // Flip on the "My shows" toggle
  const mine = page.getByRole("button", { name: /my shows/i }).first();
  if (await mine.count()) {
    await mine.click().catch(() => {});
    await pause(page, 2200);
    await mine.click().catch(() => {});
    await pause(page, 1200);
  }

  // Step forward and back one week via the chevrons
  const next = page.getByLabel(/next week/i).first();
  if (await next.count()) {
    await next.click().catch(() => {});
    await pause(page, 1800);
  }
  const prev = page.getByLabel(/previous week/i).first();
  if (await prev.count()) {
    await prev.click().catch(() => {});
    await pause(page, 1800);
  }

  await page.evaluate(() =>
    window.scrollTo({ top: 0, behavior: "smooth" })
  );
  await pause(page, 1500);
});
