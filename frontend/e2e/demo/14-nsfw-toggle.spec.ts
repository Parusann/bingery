import { test, expect } from "@playwright/test";
import { pause } from "./_helpers";

test("14 — NSFW Ecchi toggle: flip the header eye and watch counts change", async ({
  page,
}) => {
  await page.goto("/discover");
  await expect(
    page.getByRole("heading", { name: "Discover", exact: true })
  ).toBeVisible();
  await pause(page, 3000); // let user read the current grid

  const eye = page.getByRole("button", { name: /Ecchi/i });
  await eye.waitFor({ state: "visible" });
  // Click to reveal Ecchi
  await eye.click();
  await pause(page, 3500); // visibly different grid after refetch

  // Click to hide again
  await eye.click();
  await pause(page, 3000);
});
