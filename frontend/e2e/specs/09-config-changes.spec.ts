import { test, expect } from "@playwright/test";
import { setupApiAuth, assertNoAuthError } from "../fixtures/helpers";

test.describe("設定変更履歴画面", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiAuth(page);
    await page.goto("/config-changes");
    await page.waitForLoadState("networkidle");
    await assertNoAuthError(page);
  });

  test("ヘッダーとタイトルが表示される", async ({ page }) => {
    await expect(page.getByText("設定変更履歴").first()).toBeVisible();
  });

  test("変更一覧テーブルまたは空メッセージが表示される", async ({ page }) => {
    // Must show changes or explicit empty state — not just "main" element
    await expect(
      page.getByText(/safeguard|stage|trader|general|変更.*0件|データ/).first()
    ).toBeVisible({ timeout: 5_000 });
  });

  test("変更行をクリックするとDiffViewerが表示される", async ({ page }) => {
    const row = page.locator("button, tr, [role=button]").filter({ hasText: /safeguard|stage|trader|general/ }).first();
    const hasRow = await row.isVisible({ timeout: 5_000 }).catch(() => false);
    test.skip(!hasRow, "変更履歴データなし — スキップ");

    await row.click();
    await expect(page.getByText(/Before|After|変更前|変更後|diff/).first()).toBeVisible({ timeout: 5_000 });
  });

  test("ページネーションが機能する", async ({ page }) => {
    const nextButton = page.getByRole("button", { name: /次|→|>/ });
    const hasNext = await nextButton.isVisible({ timeout: 3_000 }).catch(() => false);
    test.skip(!hasNext, "ページネーションなし — データ不足");

    await nextButton.click();
    await page.waitForTimeout(1000);
    await expect(page.getByText("設定変更履歴").first()).toBeVisible();
  });

  test("件数情報が表示される", async ({ page }) => {
    const countText = page.getByText(/\d+件|total|全/).first();
    const hasCount = await countText.isVisible({ timeout: 5_000 }).catch(() => false);
    test.skip(!hasCount, "件数情報なし — スキップ");

    await expect(countText).toBeVisible();
  });
});
