import { test, expect } from "@playwright/test";

test("landing renders hero and nav", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Discover what/i })).toBeVisible();
  await expect(page.getByRole("link", { name: "Discover" })).toBeVisible();
});

test("discover loads grid", async ({ page }) => {
  await page.goto("/discover");
  await expect(page.getByRole("heading", { name: "Discover" })).toBeVisible();
});

test("404 path navigates to landing", async ({ page }) => {
  await page.goto("/does-not-exist");
  await expect(page).toHaveURL(/\/$/);
});
