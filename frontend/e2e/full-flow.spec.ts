import { test, expect } from "@playwright/test";

test("register → discover → detail navigation", async ({ page }) => {
  const suffix = Date.now();
  await page.goto("/auth");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.getByLabel("Username").fill(`e2e${suffix}`);
  await page.getByLabel("Email").fill(`e2e${suffix}@test.local`);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/discover/);

  const firstCard = page.getByRole("link").filter({ hasText: /./ }).first();
  if (await firstCard.count()) {
    await firstCard.click();
    await expect(page).toHaveURL(/\/anime\//);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  }
});
