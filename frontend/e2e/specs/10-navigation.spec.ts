import { test, expect } from "@playwright/test";
import { setupApiAuth } from "../fixtures/helpers";

test.describe("ナビゲーション", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiAuth(page);
  });

  test("ヘッダーナビでダッシュボードに遷移できる", async ({ page }) => {
    await page.goto("/settings");
    await page.getByRole("link", { name: "ダッシュボード" }).click();
    await expect(page).toHaveURL("/");
  });

  test("ヘッダーナビでトレーダー設定に遷移できる", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.getByRole("link", { name: "トレーダー設定" }).click();
    await expect(page).toHaveURL("/traders");
  });

  test("ヘッダーナビで通知設定に遷移できる", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.getByRole("link", { name: "通知設定" }).click();
    await expect(page).toHaveURL("/notifications");
  });

  test("ヘッダーナビで取引履歴に遷移できる", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.getByRole("link", { name: "取引履歴" }).click();
    await expect(page).toHaveURL("/history");
  });

  test("ヘッダーナビでシステム設定に遷移できる", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.getByRole("link", { name: "システム設定" }).click();
    await expect(page).toHaveURL("/settings");
  });

  test("ブラウザバックで前のページに戻れる", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.getByRole("link", { name: "トレーダー設定" }).click();
    await expect(page).toHaveURL("/traders");
    await page.goBack();
    await expect(page).toHaveURL("/");
  });
});
