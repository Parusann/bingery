import { test } from "@playwright/test";
import { pause, smoothScroll } from "./_helpers";

test("07 — For You: taste profile + personal recommendations", async ({
  page,
}) => {
  await page.goto("/for-you");
  // Wait for the first heading on the page (could be "For you" or taste card)
  await page.waitForLoadState("networkidle").catch(() => {});
  await pause(page, 3500); // taste bars need a beat to animate in

  // Slow scroll: profile → recommendations
  for (let i = 0; i < 4; i++) {
    await smoothScroll(page, 550, 1500);
  }
  await pause(page, 1200);

  // Scroll back to the top so the genre weights are the closing shot
  await page.evaluate(() =>
    window.scrollTo({ top: 0, behavior: "smooth" })
  );
  await pause(page, 2500);
});
