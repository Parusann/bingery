import { test, expect } from "@playwright/test";
import { pause } from "./_helpers";

test("02 — Auth page: sign-up / sign-in tabs and login flow", async ({
  page,
}) => {
  await page.goto("/auth");
  await expect(
    page.getByRole("heading", { name: "Welcome back" })
  ).toBeVisible();
  await pause(page, 2000);

  // Scope all subsequent queries to the auth form so we don't accidentally hit
  // the header's "Sign in" button.
  const form = page.locator("form").first();

  // Show the Sign-up tab
  await form.getByRole("button", { name: "Sign up", exact: true }).click();
  await pause(page, 2200);

  // Back to the Sign-in tab
  await form
    .getByRole("button", { name: "Sign in", exact: true })
    .first()
    .click();
  await pause(page, 1500);

  // Fill credentials with fill() — reliable for controlled inputs
  await form.getByLabel("Email").fill("demo@bingery.app");
  await pause(page, 700);
  await form.getByLabel("Password").fill("demo123");
  await pause(page, 1200);

  // Submit — the form's lone type="submit" button. Race with the URL change.
  await Promise.all([
    page.waitForURL("**/discover", { timeout: 20_000 }),
    form.locator('button[type="submit"]').click(),
  ]);
  await pause(page, 2200);
});
