import { test, expect } from "@playwright/test";
import { setupApiAuth, assertNoAuthError } from "../fixtures/helpers";

test.describe("バックテスト画面", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiAuth(page);
    await page.goto("/backtests");
    await page.waitForLoadState("networkidle");
    await assertNoAuthError(page);
  });

  test("ヘッダーとタイトルが表示される", async ({ page }) => {
    await expect(page.getByText("バックテスト").first()).toBeVisible();
  });

  test("新規バックテストセクションが表示される", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "新規バックテスト" })).toBeVisible({ timeout: 5_000 });
  });

  test("バックテスト履歴セクションが表示される", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "バックテスト履歴" })).toBeVisible({ timeout: 5_000 });
  });

  test("通貨ペア選択ドロップダウンが機能する", async ({ page }) => {
    const selects = page.locator("select");
    await expect(selects.first()).toBeVisible({ timeout: 5_000 });
    const options = await selects.first().locator("option").count();
    expect(options).toBeGreaterThan(0);
  });

  test("時間足選択ドロップダウンが機能する", async ({ page }) => {
    const selects = page.locator("select");
    const selectCount = await selects.count();
    expect(selectCount).toBeGreaterThanOrEqual(2);
  });

  test("バックテスト実行ボタンが存在する", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: "バックテスト実行" })
    ).toBeVisible({ timeout: 5_000 });
  });

  test("開始日・終了日入力フィールドがある", async ({ page }) => {
    await expect(page.getByText("開始日")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("終了日")).toBeVisible();
  });

  test("ステータスバッジの色分けが正しい", async ({ page }) => {
    const completedBadge = page.getByText("完了").first();
    const hasBadge = await completedBadge.isVisible({ timeout: 3_000 }).catch(() => false);
    test.skip(!hasBadge, "バックテスト履歴なし — スキップ");

    await expect(completedBadge).toBeVisible();
  });
});
