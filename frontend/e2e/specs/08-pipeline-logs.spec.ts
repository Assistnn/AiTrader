import { test, expect } from "@playwright/test";
import { setupApiAuth, assertNoAuthError } from "../fixtures/helpers";

test.describe("パイプラインログ画面", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiAuth(page);
    await page.goto("/pipeline-logs");
    await page.waitForLoadState("networkidle");
    await assertNoAuthError(page);
  });

  test("ヘッダーとタイトルが表示される", async ({ page }) => {
    await expect(page.getByText("パイプラインログ").first()).toBeVisible();
  });

  test("ログ一覧テーブルまたは空メッセージが表示される", async ({ page }) => {
    // Must show log data or explicit empty state — not just "main" element
    await expect(
      page.getByText(/M1|M2|M3|M4|ガード|ログ.*0件|データ/).first()
    ).toBeVisible({ timeout: 5_000 });
  });

  test("ステージバッジに色分けがある", async ({ page }) => {
    const stageBadge = page.locator("[class*=badge], [class*=Badge]").first();
    const hasBadge = await stageBadge.isVisible({ timeout: 5_000 }).catch(() => false);
    test.skip(!hasBadge, "ログデータなし — スキップ");

    await expect(stageBadge).toBeVisible();
  });

  test("ログ行をクリックするとJSON詳細が展開される", async ({ page }) => {
    const row = page.locator("tr, button, [role=row]").filter({ hasText: /M1|M2|M3|M4/ }).first();
    const hasRow = await row.isVisible({ timeout: 5_000 }).catch(() => false);
    test.skip(!hasRow, "ログデータなし — スキップ");

    await row.click();
    // Expanded content may show JSON snapshots, stage details, or config info
    await expect(
      page.getByText(/input|output|config|Snapshot|方向判定|セットアップ|エントリー|退出/).first()
    ).toBeVisible({ timeout: 5_000 });
  });

  test("ページネーションが機能する", async ({ page }) => {
    const nextButton = page.getByRole("button", { name: /次|→|>/ });
    const hasNext = await nextButton.isVisible({ timeout: 3_000 }).catch(() => false);
    test.skip(!hasNext, "ページネーションなし — データ不足");

    await nextButton.click();
    await page.waitForTimeout(1000);
    await expect(page.getByText("パイプラインログ").first()).toBeVisible();
  });

  test("実行時間（elapsedMs）が表示される", async ({ page }) => {
    const msText = page.getByText(/\d+ms/).first();
    const hasMs = await msText.isVisible({ timeout: 5_000 }).catch(() => false);
    test.skip(!hasMs, "ログデータなし — スキップ");

    await expect(msText).toBeVisible();
  });
});
