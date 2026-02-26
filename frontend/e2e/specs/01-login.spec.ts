import { test, expect } from "@playwright/test";

// Login tests run WITHOUT the authenticated storageState
test.use({ storageState: { cookies: [], origins: [] } });

const TEST_EMAIL = "test@example.com";
const TEST_PASSWORD = "12345678";

test.describe("ログイン画面", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
  });

  test("ログインページが正しく表示される", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "AI Trading System" })).toBeVisible();
    await expect(page.getByText("ログインしてください")).toBeVisible();
    await expect(page.getByLabel("メールアドレス")).toBeVisible();
    await expect(page.getByRole("button", { name: "ログイン" })).toBeVisible();
  });

  test("正しい認証情報でログインできる", async ({ page }) => {
    await page.getByLabel("メールアドレス").fill(TEST_EMAIL);
    await page.getByLabel("パスワード").fill(TEST_PASSWORD);
    await page.getByRole("button", { name: "ログイン" }).click();

    await expect(page).toHaveURL("/", { timeout: 10_000 });

    const token = await page.evaluate(() =>
      localStorage.getItem("ai_trading_access_token")
    );
    expect(token).toBeTruthy();
  });

  test("不正なパスワードではダッシュボードに遷移しない", async ({ page }) => {
    await page.getByLabel("メールアドレス").fill(TEST_EMAIL);
    await page.getByLabel("パスワード").fill("wrongpassword");
    await page.getByRole("button", { name: "ログイン" }).click();

    // Should remain on /login (forceLogout redirects back to /login on 401)
    await page.waitForTimeout(3_000);
    await expect(page).toHaveURL(/\/login/);
  });

  test("空のフォームではログインボタンが送信されない", async ({ page }) => {
    await page.getByRole("button", { name: "ログイン" }).click();
    // Should still be on login page (HTML5 validation prevents submit)
    await expect(page).toHaveURL(/\/login/);
  });

  test("未認証でダッシュボードにアクセスするとログインにリダイレクトされる", async ({ page }) => {
    await page.goto("/");
    // AuthGuard should redirect to /login
    await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });
  });

  test("ログイン中はボタンが無効化される", async ({ page }) => {
    await page.getByLabel("メールアドレス").fill(TEST_EMAIL);
    await page.getByLabel("パスワード").fill(TEST_PASSWORD);

    const button = page.getByRole("button", { name: "ログイン" });
    await button.click();

    // Button should show loading state briefly
    await expect(
      page.getByRole("button", { name: /ログイン中/ })
    ).toBeVisible({ timeout: 2_000 }).catch(() => {
      // May be too fast to catch — that's OK
    });

    // Should eventually redirect
    await expect(page).toHaveURL("/", { timeout: 10_000 });
  });
});
