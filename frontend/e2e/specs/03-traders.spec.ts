import { test, expect } from "@playwright/test";
import { setupApiAuth, assertNoAuthError } from "../fixtures/helpers";

// Helper: click on the first actual trader (not the "新規トレーダー追加" button)
async function selectFirstTrader(page: import("@playwright/test").Page) {
  const traderButton = page.getByRole("button", { name: /FX-|CRYPTO-/ }).first();
  await expect(traderButton).toBeVisible({ timeout: 10_000 });
  await traderButton.click();
  // Wait for tabs to render after selection
  await page.waitForTimeout(500);
}

// Helper: find tab button (custom Tabs component uses plain <button>, not role="tab")
function getTab(page: import("@playwright/test").Page, name: string) {
  return page.locator("button").filter({ hasText: name }).first();
}

test.describe("トレーダー設定画面", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiAuth(page);
    await page.goto("/traders");
    await page.waitForLoadState("networkidle");
    await assertNoAuthError(page);
  });

  // --- Layout ---
  test("左ペインにトレーダーリストが表示される", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "トレーダー一覧" })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("新規トレーダー追加")).toBeVisible();
  });

  test("トレーダー未選択時にプレースホルダーが表示される", async ({ page }) => {
    await expect(
      page.getByText("左のリストからトレーダーを選択してください")
    ).toBeVisible();
  });

  // --- Trader Selection ---
  test("トレーダーを選択するとタブが表示される", async ({ page }) => {
    await selectFirstTrader(page);
    await expect(getTab(page, "基本情報")).toBeVisible({ timeout: 5_000 });
    await expect(getTab(page, "M1-M2")).toBeVisible();
  });

  // --- Tabs ---
  test("5つのタブが表示される", async ({ page }) => {
    await selectFirstTrader(page);
    await expect(getTab(page, "基本情報")).toBeVisible({ timeout: 5_000 });
    await expect(getTab(page, "M1-M2")).toBeVisible();
    await expect(getTab(page, "M3-M4")).toBeVisible();
    await expect(getTab(page, "MX")).toBeVisible();
    await expect(getTab(page, "セーフガード")).toBeVisible();
  });

  test("基本情報タブの内容が表示される", async ({ page }) => {
    await selectFirstTrader(page);
    await expect(getTab(page, "基本情報")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText(/取引タイプ|通貨ペア|資金/).first()).toBeVisible({ timeout: 5_000 });
  });

  test("M1-M2タブに切替できる", async ({ page }) => {
    await selectFirstTrader(page);
    await getTab(page, "M1-M2").click();
    await expect(page.getByText(/M1|方向判定|タイムフレーム/).first()).toBeVisible({ timeout: 5_000 });
  });

  test("M3-M4タブに切替できる", async ({ page }) => {
    await selectFirstTrader(page);
    await getTab(page, "M3-M4").click();
    await expect(page.getByText(/M3|エントリー|タイムフレーム/).first()).toBeVisible({ timeout: 5_000 });
  });

  test("MXタブに切替できる", async ({ page }) => {
    await selectFirstTrader(page);
    await getTab(page, "MX").click();
    await expect(page.getByText("MX: 統合判定")).toBeVisible({ timeout: 5_000 });
  });

  test("セーフガードタブに切替できる", async ({ page }) => {
    await selectFirstTrader(page);
    await getTab(page, "セーフガード").click();
    await expect(page.getByText(/セーフガードルール|SG-/).first()).toBeVisible({ timeout: 5_000 });
  });

  // --- CRUD ---
  test("新規トレーダー作成フォームが開閉できる", async ({ page }) => {
    await page.getByText("新規トレーダー追加").click();
    await expect(page.getByPlaceholder("トレーダー名")).toBeVisible();
    await page.getByText("新規トレーダー追加").click();
    await expect(page.getByPlaceholder("トレーダー名")).not.toBeVisible();
  });

  test("保存ボタンと削除ボタンが表示される", async ({ page }) => {
    await selectFirstTrader(page);
    await expect(page.getByRole("button", { name: /保存/ })).toBeVisible({ timeout: 5_000 });
    await expect(page.getByRole("button", { name: /削除/ })).toBeVisible();
  });
});
