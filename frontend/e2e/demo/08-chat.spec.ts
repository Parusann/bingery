import { test, expect } from "@playwright/test";
import { pause } from "./_helpers";

test("08 — Guide recommends anime and refines its picks", async ({ page }) => {
  test.setTimeout(330_000);
  await page.goto("/chat");
  const composer = page.getByRole("textbox", { name: "Message the guide" });
  const send = page.getByRole("button", { name: "Send", exact: true });

  for (const message of ["Recommend me a short anime like Steins;Gate.", "Which of those has the strongest mystery?"]) {
    const log = page.getByRole("log", { name: "Conversation" });
    const response = page.waitForResponse((r) => r.url().endsWith("/api/chat/message") &&
      r.request().method() === "POST", { timeout: 150_000 });
    await composer.fill(message);
    await send.click();
    expect((await response).ok()).toBe(true);
    await expect(composer).toBeEnabled();
    await expect(log.getByText(message, { exact: true })).toBeVisible();
    await pause(page, 2000);
  }
});
