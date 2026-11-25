import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

test("verify an invite, save an anime, and share its collection with a guest", async ({ page, browser, baseURL }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));

  await page.goto("/auth?email=viewer%40example.test&invite=browse-invite");
  await page.getByLabel("Username", { exact: true }).fill("viewer");
  await page.getByLabel("Password", { exact: true }).fill("browser-test-password");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Check your email" })).toBeVisible();
  const mail = await readFile(process.env.BINGERY_E2E_MAIL!, "utf8");
  const code = /Verification code for viewer@example\.test: (\d{6})/.exec(mail)?.[1];
  expect(code).toBeTruthy();
  await page.getByLabel("Verification code").fill(code!);
  await page.getByRole("button", { name: "Verify", exact: true }).click();
  await expect(page).toHaveURL(/\/discover$/);

  await page.getByRole("link", { name: /Spirited Away/ }).first().click();
  await expect(page.getByRole("heading", { level: 1, name: "Spirited Away" })).toBeVisible();
  await page.getByRole("button", { name: "Rate 9 of 10", exact: true }).click();
  await page.getByRole("button", { name: "Save rating" }).click();
  await expect(page.getByRole("button", { name: "Saved", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Watching", exact: true }).click();
  await page.getByRole("spinbutton", { name: "Episodes watched" }).fill("1");
  await page.getByRole("button", { name: "Save progress" }).click();
  await expect(page.getByText("Progress saved", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Add to collection" }).click();
  const picker = page.getByRole("dialog", { name: "Add to collection" });
  await picker.getByLabel("New collection name").fill("Weekend films");
  await picker.getByRole("button", { name: "Create and add" }).click();
  await expect(picker.getByRole("button", { name: /Weekend films.*Added/ })).toBeVisible();
  await page.keyboard.press("Escape");

  await page.goto("/watchlist");
  await expect(page.getByRole("link", { name: /Spirited Away/ })).toBeVisible();
  await page.goto("/collections");
  await page.getByRole("link", { name: /Weekend films/ }).click();
  await page.getByRole("button", { name: "Edit", exact: true }).click();
  await page.getByRole("checkbox", { name: /Public/ }).check();
  await page.getByRole("button", { name: "Save changes" }).click();
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.getByRole("button", { name: "Copy share link" }).click();
  await expect(page.getByRole("button", { name: "Link copied" })).toBeVisible();
  const url = await page.evaluate(() => navigator.clipboard.readText());
  expect(url.startsWith(baseURL + "/collections/share/")).toBe(true);

  const guest = await browser.newContext();
  try {
    const publicPage = await guest.newPage();
    await publicPage.goto(url);
    await expect(publicPage.getByRole("heading", { name: "Weekend films" })).toBeVisible();
    await expect(publicPage.getByRole("link", { name: /Spirited Away/ })).toBeVisible();
    await expect(publicPage.getByRole("button", { name: "Edit", exact: true })).toHaveCount(0);

    await page.getByRole("button", { name: "Edit", exact: true }).click();
    await page.getByRole("checkbox", { name: /Public/ }).uncheck();
    await page.getByRole("button", { name: "Save changes" }).click();
    await expect(page.getByRole("button", { name: /share link|Link copied/ })).toHaveCount(0);
    await publicPage.reload();
    await expect(publicPage.getByRole("heading", { name: "Collection unavailable" })).toBeVisible();
  } finally {
    await guest.close();
  }
  await page.goto("/stats");
  await expect(page.getByRole("heading", { name: "Your rhythm" })).toBeVisible();
  await expect(page.getByText("9.0/10", { exact: true })).toBeVisible();
  await page.goto("/activity");
  await expect(page.getByText("Rated Spirited Away", { exact: true })).toBeVisible();
  await page.goto("/seasonal");
  await expect(page.getByRole("button", { name: "Previous year" })).toBeVisible();
  await page.goto("/for-you");
  await expect(page.getByRole("heading", { name: "For you", exact: true })).toBeVisible();
  await page.goto("/compare");
  await page.getByLabel("Anime A", { exact: true }).fill("Spirited");
  await page.getByRole("button", { name: /Spirited Away/ }).click();
  await page.getByLabel("Anime B", { exact: true }).fill("Castle");
  await page.getByRole("button", { name: /Castle in the Sky/ }).click();
  await expect(page.getByText("Shared genres", { exact: true })).toBeVisible();

  await page.route("**/api/schedule/week?**", (route) => route.fulfill({ status: 503, json: { error: "Offline" } }));
  await page.goto("/schedule?week=2026-11-22");
  await expect(page.getByRole("alert")).toContainText("This week’s schedule couldn’t load.");
  await page.unroute("**/api/schedule/week?**");
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByRole("heading", { name: /Sunday, November 22/i })).toBeVisible();
  expect(errors).toEqual([]);
});
