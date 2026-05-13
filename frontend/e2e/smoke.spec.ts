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

test("seasonal page loads", async ({ page }) => {
  await page.goto("/seasonal");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});

test("collections shows sign-in gate when logged out", async ({ page }) => {
  await page.goto("/collections");
  await expect(
    page.getByRole("heading", { name: /Sign in to build/i })
  ).toBeVisible();
});

test("stats shows sign-in gate when logged out", async ({ page }) => {
  await page.goto("/stats");
  await expect(
    page.getByRole("heading", { name: /Sign in for your stats/i })
  ).toBeVisible();
});

test("404 path navigates to landing", async ({ page }) => {
  await page.goto("/does-not-exist");
  await expect(page).toHaveURL(/\/$/);
});
