import { test, expect } from "@playwright/test";

test("landing renders hero and nav", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Discover what/i })).toBeVisible();
  await expect(page.getByRole("link", { name: "Browse anime" })).toBeVisible();
});

test("discover loads grid", async ({ page }) => {
  await page.goto("/discover");
  await expect(page.getByRole("heading", { name: "Discover" })).toBeVisible();
});

test("seasonal offers signed-out visitors access to their account", async ({ page }) => {
  await page.goto("/seasonal");
  await expect(page.getByRole("heading", { name: "Sign in to browse the season" })).toBeVisible();
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

test("mobile navigation restores focus and keeps the layout inside the viewport", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const more = page.getByRole("button", { name: "More", exact: true });
  await more.click();
  const dialog = page.getByRole("dialog", { name: "More", exact: true });
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(more).toBeFocused();
  await more.click();
  await dialog.getByRole("link", { name: "Collections" }).click();
  await expect(page.getByRole("heading", { name: "Sign in to build collections" })).toBeVisible();
  await page.getByRole("main").getByRole("link", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/auth$/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("invalid schedule dates recover and signed-out pages skip private data requests", async ({ page }) => {
  const privateRequests: string[] = [];
  page.on("request", (r) => {
    if (/\/api\/(?:schedule\/week|collections)(?:\?|$)/.test(r.url())) privateRequests.push(r.url());
  });
  await page.goto("/schedule?week=garbage&lang=invalid");
  await expect(page.getByRole("heading", { name: "Sign in to see the schedule" })).toBeVisible();
  await expect(page).toHaveURL(/week=\d{4}-\d{2}-\d{2}&lang=both/);
  await page.goto("/collections");
  await expect(page.getByRole("heading", { name: "Sign in to build collections" })).toBeVisible();
  expect(privateRequests).toEqual([]);
});

test("guide retries a failed message and sends each turn to the provider once", async ({ page }) => {
  const requests: { message: string; conversation: { role: string; content: string }[] }[] = [];
  await page.route("**/api/chat/message", (route) => {
    requests.push(route.request().postDataJSON());
    return requests.length === 1
      ? route.fulfill({ status: 503, json: { error: "Try again later.", stop_reason: "provider_unavailable" } })
      : route.fulfill({ json: { response: "Try a mystery series." } });
  });
  await page.goto("/chat");
  const composer = page.getByRole("textbox", { name: "Message the guide" });
  await composer.fill("Recommend a mystery.");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText("Taste guide is offline")).toBeVisible();
  await page.getByRole("button", { name: "Retry message" }).click();
  await expect(page.getByRole("log").getByText("Try a mystery series.")).toBeVisible();
  await expect(page.getByRole("log").getByText("Recommend a mystery.", { exact: true })).toHaveCount(1);
  await composer.fill("A shorter one?");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByRole("log").getByText("Try a mystery series.")).toHaveCount(2);
  expect(requests[0].conversation).toEqual([]);
  expect(requests[1]).toEqual(requests[0]);
  expect(requests[2].conversation).toEqual([
    { role: "user", content: "Recommend a mystery." },
    { role: "assistant", content: "Try a mystery series." },
  ]);
});
