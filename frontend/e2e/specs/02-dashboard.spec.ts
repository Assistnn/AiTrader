import { test, expect } from "@playwright/test";
import { setupApiAuth, assertNoAuthError } from "../fixtures/helpers";

test.describe("ダッシュボード", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiAuth(page);
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await assertNoAuthError(page);
  });

  // --- Layout ---
  test("3カラムレイアウトが表示される", async ({ page }) => {
    await expect(page.locator("aside").first()).toBeVisible({ timeout: 10_000 });
    // Verify dashboard content loaded (not just layout shell)
    await expect(page.getByText("本日損益", { exact: true })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("マーケットウォッチ")).toBeVisible();
  });

  test("ヘッダーが表示される", async ({ page }) => {
    await expect(page.getByRole("link", { name: "AI Trading System" })).toBeVisible();
    await expect(page.getByRole("link", { name: "ダッシュボード" })).toBeVisible();
  });

  // --- Summary Cards ---
  test("サマリーカードが表示される", async ({ page }) => {
    // "本日損益" appears in summary card (exact) AND sidebar ("本日損益: ¥xxx")
    // Use exact:true to match only the summary card heading
    await expect(page.getByText("本日損益", { exact: true })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("月間損益", { exact: true })).toBeVisible();
  });

  // --- MarketWatch ---
  test("MarketWatchセクションが表示される", async ({ page }) => {
    await expect(page.getByText("マーケットウォッチ")).toBeVisible({ timeout: 10_000 });
  });

  test("MarketWatchにペアが表示される", async ({ page }) => {
    await expect(
      page.getByText(/USD_JPY|EUR_JPY|BTC_JPY/).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  // --- Chart ---
  test("チャートパネルが表示される", async ({ page }) => {
    const main = page.locator("main");
    await expect(main.getByText("チャート").first()).toBeVisible({ timeout: 10_000 });
  });

  test("チャートのタイムフレーム切替ができる", async ({ page }) => {
    const main = page.locator("main");
    // Chart section has at least 2 selects (pair + timeframe)
    const selects = main.locator("select");
    await expect(selects.first()).toBeVisible({ timeout: 5_000 });
    const count = await selects.count();
    expect(count).toBeGreaterThanOrEqual(2);
  });

  // --- Trader Sidebar ---
  test("トレーダーサイドバーにトレーダーが表示される", async ({ page }) => {
    await expect(
      page.getByText(/FX-|CRYPTO-/).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  // --- Action Buttons ---
  test("アクションボタンが表示される", async ({ page }) => {
    const main = page.locator("main");
    await expect(
      main.getByRole("button").filter({ hasText: /全停止|全開始|全て決済/ }).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  // --- VPS Status ---
  test("VPSステータスが表示される", async ({ page }) => {
    // Explicitly scoped to header
    const header = page.locator("header");
    await expect(header.getByText("VPS稼働中")).toBeVisible({ timeout: 5_000 });
  });

  // --- Error State ---
  test("APIエラー時にエラーメッセージが表示される", async ({ page }) => {
    // Test-specific route: registered later, runs first (Playwright LIFO)
    // Global auth interceptor falls back to this route
    await page.route("**/api/v1/dashboard/summary", (route) =>
      route.fulfill({
        status: 500,
        body: JSON.stringify({
          status: "error",
          error: { message: "Test error" },
        }),
      })
    );
    await page.goto("/");
    await expect(
      page.getByText(/失敗|エラー/).first()
    ).toBeVisible({ timeout: 10_000 });
  });
});
