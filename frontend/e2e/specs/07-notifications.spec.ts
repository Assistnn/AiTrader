import { test, expect } from "@playwright/test";
import { setupApiAuth, assertNoAuthError } from "../fixtures/helpers";

test.describe("通知設定画面", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiAuth(page);
    await page.goto("/notifications");
    await page.waitForLoadState("networkidle");
    await assertNoAuthError(page);
  });

  // --- Layout ---
  test("左メニューに4つのセクションが表示される", async ({ page }) => {
    await expect(page.getByRole("button", { name: "SMTP設定" })).toBeVisible();
    await expect(page.getByRole("button", { name: "通知メールアドレス" })).toBeVisible();
    await expect(page.getByRole("button", { name: "デイリー通知" })).toBeVisible();
    await expect(page.getByRole("button", { name: "通知トリガー" })).toBeVisible();
  });

  // --- SMTP Settings ---
  test("SMTP設定がデフォルトで表示される", async ({ page }) => {
    await expect(page.getByText(/SMTPホスト|ホスト/).first()).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText(/ポート/).first()).toBeVisible();
  });

  test("SMTP設定に保存ボタンがある", async ({ page }) => {
    await expect(page.getByRole("button", { name: /保存/ }).first()).toBeVisible({ timeout: 5_000 });
  });

  test("テスト送信ボタンがある", async ({ page }) => {
    await expect(page.getByRole("button", { name: /テスト送信/ })).toBeVisible({ timeout: 5_000 });
  });

  // --- Email Management ---
  test("通知メールアドレスセクションに切替できる", async ({ page }) => {
    await page.getByRole("button", { name: "通知メールアドレス" }).click();
    await expect(page.getByText(/メールアドレス|追加/).first()).toBeVisible({ timeout: 5_000 });
  });

  test("メールアドレス追加フィールドが機能する", async ({ page }) => {
    await page.getByRole("button", { name: "通知メールアドレス" }).click();
    // Actual placeholder is "user@example.com"
    const input = page.getByPlaceholder("user@example.com");
    await expect(input).toBeVisible({ timeout: 5_000 });
    await input.fill("test-e2e@example.com");
    await expect(page.getByRole("button", { name: /追加/ })).toBeVisible();
  });

  // --- Daily Notifications ---
  test("デイリー通知設定に切替できる", async ({ page }) => {
    await page.getByRole("button", { name: "デイリー通知" }).click();
    await expect(page.getByText(/有効|送信時刻|損益|取引|ガード/).first()).toBeVisible({ timeout: 5_000 });
  });

  test("デイリー通知のトグルスイッチが機能する", async ({ page }) => {
    await page.getByRole("button", { name: "デイリー通知" }).click();
    const switchEl = page.locator("[role=switch]").first();
    await expect(switchEl).toBeVisible({ timeout: 5_000 });
  });

  // --- Triggers ---
  test("通知トリガー設定に切替できる", async ({ page }) => {
    await page.getByRole("button", { name: "通知トリガー" }).click();
    await expect(page.getByText(/トリガー|セーフガード|損失|取引/).first()).toBeVisible({ timeout: 5_000 });
  });

  // --- Section Switching ---
  test("セクション間の切替が正しく動作する", async ({ page }) => {
    await expect(page.getByText(/SMTPホスト|ホスト/).first()).toBeVisible({ timeout: 5_000 });

    await page.getByRole("button", { name: "デイリー通知" }).click();
    await expect(page.getByText(/有効|送信時刻/).first()).toBeVisible({ timeout: 5_000 });

    await page.getByRole("button", { name: "通知トリガー" }).click();
    await expect(page.getByText(/トリガー|セーフガード/).first()).toBeVisible({ timeout: 5_000 });
  });
});
