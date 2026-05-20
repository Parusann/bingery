import { test as setup, expect } from "@playwright/test";

const authFile = "e2e/demo/.auth/demo.json";

setup("authenticate as demo user (Mio)", async ({ page, request }) => {
  // Pin to 127.0.0.1 so we never trip over localhost→::1 (IPv6) on Windows
  // when Flask is only bound to IPv4. This bit us during a re-run.
  const res = await request.post("http://127.0.0.1:5000/api/auth/login", {
    data: { email: "demo@bingery.app", password: "demo123" },
    headers: { "Content-Type": "application/json" },
  });
  expect(res.ok(), `login failed: ${res.status()}`).toBeTruthy();
  const body = await res.json();
  const token: string = body.token;

  await page.goto("/");
  await page.evaluate((t) => {
    localStorage.setItem("bingery_token", t);
  }, token);
  await page.reload();

  await page.context().storageState({ path: authFile });
});
