import { test } from "@playwright/test";
import { pause, smoothScroll } from "./_helpers";

test("10 — Watchlist: tabs across watching/planning/completed", async ({
  page,
}) => {
  await page.goto("/watchlist");
  await page.waitForLoadState("networkidle").catch(() => {});
  await pause(page, 2500);

  // Try clicking common tab labels — gracefully no-op if absent
  for (const tab of ["Watching", "Planning", "Completed", "Paused", "Dropped"]) {
    const btn = page.getByRole("button", { name: tab, exact: true });
    if (await btn.count()) {
      await btn.first().click().catch(() => {});
      await pause(page, 1800);
    }
  }
  await smoothScroll(page, 500, 1400);
  await pause(page, 1500);
});
