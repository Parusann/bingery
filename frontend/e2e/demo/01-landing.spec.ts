import { test } from "@playwright/test";
import { pause, smoothScrollFrame } from "./_helpers";

test("01 — Landing page hero, features, and footer", async ({ page }) => {
  await page.goto("/");
  // The landing is an iframe wrapper around frontend/public/landing.html
  const iframeEl = await page.waitForSelector("iframe", { state: "attached" });
  const frame = await iframeEl.contentFrame();
  if (!frame) throw new Error("landing iframe missing");
  await frame.waitForLoadState("domcontentloaded");
  await pause(page, 2500);

  // Slow scroll through the hero, features, and footer
  for (let i = 0; i < 6; i++) {
    await smoothScrollFrame(frame, 520, 1400);
  }
  await pause(page, 1500);

  // Scroll back to top so the recording ends on the hero
  await frame.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  await pause(page, 2000);
});
