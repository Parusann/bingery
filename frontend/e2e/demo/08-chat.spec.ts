import { test, expect } from "@playwright/test";
import { pause, typeSlowly } from "./_helpers";

// Showcase all three chat modes — Recommend, Rate with AI, Onboard — each
// gets a real Ollama round-trip so the recording captures the differing
// behavior baked into MODE_PROMPTS in routes/chatbot_tools.py.
test("08 — Chat: Recommend, Rate with AI, and Onboard modes", async ({
  page,
}) => {
  test.setTimeout(600_000); // 3 Ollama round-trips on a small local model

  const inputSel = 'input[placeholder*="Tell me"]';
  const input = page.getByPlaceholder(/Tell me what you're in the mood for/i);

  async function sendAndWait(text: string) {
    await input.click();
    await page.locator(inputSel).first().fill(""); // clear if previous text lingered
    await typeSlowly(page, inputSel, text);
    await pause(page, 800);
    const before = await page.locator('p, .markdown, strong').count();
    await page.keyboard.press("Enter");
    // Wait until either a new bold title, an anime card, or new text appears
    await page
      .waitForFunction(
        (prev) =>
          document.querySelectorAll('a[href^="/anime/"]').length > 0 ||
          document.querySelectorAll("strong").length > prev + 1 ||
          document.querySelectorAll("p").length > prev + 1,
        before,
        { timeout: 150_000, polling: 1000 }
      )
      .catch(() => {});
    await pause(page, 4000);
  }

  await page.goto("/chat");
  await pause(page, 2000);
  // Make sure all three mode pills are visible up front
  await expect(page.getByRole("button", { name: "Recommend" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Rate with AI" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Onboard" })).toBeVisible();
  await pause(page, 2000);

  // ── 1. RECOMMEND mode ───────────────────────────────────────────────
  await page.getByRole("button", { name: "Recommend" }).click();
  await pause(page, 1000);
  await sendAndWait("Recommend me a short anime like Steins;Gate");

  // ── 2. RATE WITH AI mode ────────────────────────────────────────────
  await page.getByRole("button", { name: "Rate with AI" }).click();
  await pause(page, 1200);
  await sendAndWait("I just finished Frieren — help me rate it");

  // ── 3. ONBOARD mode ─────────────────────────────────────────────────
  await page.getByRole("button", { name: "Onboard" }).click();
  await pause(page, 1200);
  await sendAndWait("I'm new — help me build my taste profile");

  // End on the mode pills so viewers see all three
  await page.evaluate(() =>
    window.scrollTo({ top: 0, behavior: "smooth" })
  );
  await pause(page, 2500);
});
