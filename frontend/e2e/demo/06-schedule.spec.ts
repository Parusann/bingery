import { test, expect } from "@playwright/test";
import { pause, smoothScroll } from "./_helpers";

test("06 — Schedule: upcoming sub/dub episodes", async ({ page }) => {
  await page.goto("/schedule");
  await expect(
    page.getByRole("heading", { name: /Upcoming episodes/i })
  ).toBeVisible({ timeout: 15_000 });
  await pause(page, 2500);

  await smoothScroll(page, 500, 1300);
  await pause(page, 800);

  // Toggle through sub / dub / both
  for (const label of ["dub", "both", "sub"] as const) {
    const btn = page.getByRole("button", { name: label, exact: true }).first();
    if (await btn.count()) {
      await btn.click().catch(() => {});
      await pause(page, 2200);
    }
  }

  await page.evaluate(() =>
    window.scrollTo({ top: 0, behavior: "smooth" })
  );
  await pause(page, 1500);
});
