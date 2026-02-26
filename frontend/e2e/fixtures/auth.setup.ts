import { test as setup, expect } from "@playwright/test";

const TEST_EMAIL = process.env.E2E_EMAIL ?? "test@example.com";
const TEST_PASSWORD = process.env.E2E_PASSWORD ?? "12345678";

setup("authenticate", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("メールアドレス").fill(TEST_EMAIL);
  await page.getByLabel("パスワード").fill(TEST_PASSWORD);
  await page.getByRole("button", { name: "ログイン" }).click();

  // Wait for redirect to dashboard
  await expect(page).toHaveURL("/", { timeout: 10_000 });

  // Verify tokens are stored
  const accessToken = await page.evaluate(() =>
    localStorage.getItem("ai_trading_access_token")
  );
  expect(accessToken).toBeTruthy();

  await page.context().storageState({ path: "e2e/.auth/user.json" });
});
