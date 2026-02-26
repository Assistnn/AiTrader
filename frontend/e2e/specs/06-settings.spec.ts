import { test, expect } from "@playwright/test";
import { setupApiAuth, assertNoAuthError } from "../fixtures/helpers";

test.describe("システム設定画面", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiAuth(page);
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");
    await assertNoAuthError(page);
  });

  // --- Layout ---
  test("左メニューに5つのセクションが表示される", async ({ page }) => {
    await expect(page.getByRole("button", { name: "取引所API設定" })).toBeVisible();
    await expect(page.getByRole("button", { name: "AI API設定" })).toBeVisible();
    await expect(page.getByRole("button", { name: "セーフガード設定" })).toBeVisible();
    await expect(page.getByRole("button", { name: "コスト管理" })).toBeVisible();
    await expect(page.getByRole("button", { name: "アカウント設定" })).toBeVisible();
  });

  test("サブリンクが表示される", async ({ page }) => {
    await expect(page.getByRole("link", { name: "バックテスト" })).toBeVisible();
    await expect(page.getByRole("link", { name: "パイプラインログ" })).toBeVisible();
    await expect(page.getByRole("link", { name: "設定変更履歴" })).toBeVisible();
  });

  // --- Exchange Settings ---
  test("取引所API設定がデフォルトで表示される", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "GMOコイン" })).toBeVisible({ timeout: 5_000 });
    await expect(page.getByRole("heading", { name: "bitbank" })).toBeVisible();
  });

  test("取引所設定にAPIキー入力フィールドがある", async ({ page }) => {
    await expect(page.getByText("APIキー").first()).toBeVisible();
    await expect(page.getByText("シークレットキー").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "保存" }).first()).toBeVisible();
  });

  // --- AI Settings ---
  test("AI API設定に切替できる", async ({ page }) => {
    await page.getByRole("button", { name: "AI API設定" }).click();
    await expect(page.getByText("OpenAI")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("Google Gemini")).toBeVisible();
    await expect(page.getByText("Anthropic")).toBeVisible();
  });

  test("AI設定にモデル選択フィールドがある", async ({ page }) => {
    await page.getByRole("button", { name: "AI API設定" }).click();
    await expect(page.getByText("デフォルトモデル").first()).toBeVisible({ timeout: 5_000 });
  });

  // --- Safeguard Settings ---
  test("セーフガード設定に切替できる", async ({ page }) => {
    await page.getByRole("button", { name: "セーフガード設定" }).click();
    await expect(page.getByText("トレーダー選択")).toBeVisible({ timeout: 5_000 });
  });

  // --- Cost Settings ---
  test("コスト管理設定が読み取り専用で表示される", async ({ page }) => {
    await page.getByRole("button", { name: "コスト管理" }).click();
    await expect(page.getByText("日次トークン上限")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("サーバー環境変数で管理")).toBeVisible();
    const inputs = page.locator("input[disabled]");
    expect(await inputs.count()).toBeGreaterThan(0);
  });

  // --- Account Settings ---
  test("アカウント設定に切替できる", async ({ page }) => {
    await page.getByRole("button", { name: "アカウント設定" }).click();
    await expect(page.getByText("表示名")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("メールアドレス")).toBeVisible();
    await expect(page.getByRole("button", { name: "更新" })).toBeVisible();
  });

  // --- Section Switching ---
  test("セクション切替時に内容が更新される", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "GMOコイン" })).toBeVisible({ timeout: 5_000 });

    await page.getByRole("button", { name: "コスト管理" }).click();
    await expect(page.getByText("日次トークン上限")).toBeVisible({ timeout: 5_000 });

    await page.getByRole("button", { name: "アカウント設定" }).click();
    await expect(page.getByText("表示名")).toBeVisible({ timeout: 5_000 });
  });

  // --- Sub links navigation ---
  test("サブリンクをクリックすると対応ページに遷移する", async ({ page }) => {
    await page.getByRole("link", { name: "パイプラインログ" }).click();
    await expect(page).toHaveURL(/\/pipeline-logs/);
  });
});
