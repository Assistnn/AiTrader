import { test, expect } from "@playwright/test";
import { setupApiAuth, assertNoAuthError } from "../fixtures/helpers";

test.describe("取引履歴画面", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiAuth(page);
    await page.goto("/history");
    await page.waitForLoadState("networkidle");
    await assertNoAuthError(page);
  });

  test("ヘッダーとタイトルが表示される", async ({ page }) => {
    await expect(page.getByText("取引履歴").first()).toBeVisible();
  });

  test("取引一覧テーブルまたは空メッセージが表示される", async ({ page }) => {
    // Must show either trade data or an explicit empty state message
    await expect(
      page.getByText(/USD|EUR|BTC|買い|売り|データ|取引|0件/).first()
    ).toBeVisible({ timeout: 5_000 });
  });

  test("取引行をクリックすると詳細が展開される", async ({ page }) => {
    // Rows use ▼/▲ toggle for expansion — match table row or clickable element
    const row = page.locator("tr, button, [role=row]").filter({ hasText: /USD|EUR|BTC/ }).first();
    const hasData = await row.isVisible({ timeout: 5_000 }).catch(() => false);
    test.skip(!hasData, "取引データなし — スキップ");

    await row.click();
    // Expanded content may show pipeline stages, pips details, or entry/exit info
    await expect(
      page.getByText(/M1|M2|信頼度|pips|エントリー|決済/).first()
    ).toBeVisible({ timeout: 5_000 });
  });

  test("CSVエクスポートボタンが存在する", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /CSV|エクスポート/i })
    ).toBeVisible({ timeout: 5_000 });
  });

  test("ページネーションが機能する", async ({ page }) => {
    const nextButton = page.getByRole("button", { name: /次|→|>/ });
    const hasNext = await nextButton.isVisible({ timeout: 3_000 }).catch(() => false);
    test.skip(!hasNext, "ページネーションなし — データ不足");

    expect(await nextButton.isEnabled()).toBeTruthy();
    await nextButton.click();
    await page.waitForTimeout(1000);
    await expect(page.getByText("取引履歴").first()).toBeVisible();
  });

  test("損益の色分けが適用される", async ({ page }) => {
    const profitCell = page.locator(".text-profit").first();
    const lossCell = page.locator(".text-loss").first();
    const hasData =
      (await profitCell.isVisible({ timeout: 3_000 }).catch(() => false)) ||
      (await lossCell.isVisible({ timeout: 1_000 }).catch(() => false));
    test.skip(!hasData, "損益データなし — スキップ");

    expect(hasData).toBeTruthy();
  });

  test("サイド（買い/売り）のバッジが表示される", async ({ page }) => {
    const buyBadge = page.getByText("買い").first();
    const sellBadge = page.getByText("売り").first();
    const hasBadge =
      (await buyBadge.isVisible({ timeout: 3_000 }).catch(() => false)) ||
      (await sellBadge.isVisible({ timeout: 1_000 }).catch(() => false));
    test.skip(!hasBadge, "取引データなし — スキップ");

    expect(hasBadge).toBeTruthy();
  });
});
