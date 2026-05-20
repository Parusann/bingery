import type { Page, Frame } from "@playwright/test";

export async function pause(page: Page, ms = 1500) {
  await page.waitForTimeout(ms);
}

export async function smoothScroll(
  page: Page,
  deltaY: number,
  settleMs = 1500
) {
  await page.evaluate(
    (d) => window.scrollBy({ top: d, behavior: "smooth" }),
    deltaY
  );
  await page.waitForTimeout(settleMs);
}

export async function smoothScrollFrame(
  frame: Frame,
  deltaY: number,
  settleMs = 1500
) {
  await frame.evaluate(
    (d) => window.scrollBy({ top: d, behavior: "smooth" }),
    deltaY
  );
  await frame.waitForTimeout(settleMs);
}

export async function typeSlowly(page: Page, selector: string, text: string) {
  await page.locator(selector).first().pressSequentially(text, { delay: 60 });
}
