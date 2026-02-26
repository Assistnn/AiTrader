import { test, expect } from "@playwright/test";
import { setupApiAuth } from "../fixtures/helpers";

test.describe("テーマ切替", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiAuth(page);
  });

  test("テーマトグルボタンが表示される", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    // ThemeToggle button should be visible in the header
    const themeButton = page.locator("header button").filter({ has: page.locator("svg") }).last();
    await expect(themeButton).toBeVisible({ timeout: 5_000 });
  });

  test("テーマを切替できる", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Get initial theme
    const initialClass = await page.locator("html").getAttribute("class");

    // Find and click theme toggle (icon-only button in header)
    const themeButton = page.locator("header button").filter({ has: page.locator("svg") });
    const buttons = await themeButton.all();
    for (const btn of buttons) {
      const text = await btn.textContent();
      if (!text || text.trim() === "") {
        await btn.click();
        break;
      }
    }

    await page.waitForTimeout(500);
    const newClass = await page.locator("html").getAttribute("class");
    expect(newClass).not.toBe(initialClass);
  });

  test("テーマ設定がページ遷移後も維持される", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Switch theme
    const themeButton = page.locator("header button").filter({ has: page.locator("svg") });
    const buttons = await themeButton.all();
    for (const btn of buttons) {
      const text = await btn.textContent();
      if (!text || text.trim() === "") {
        await btn.click();
        break;
      }
    }
    await page.waitForTimeout(500);

    const themeAfterToggle = await page.locator("html").getAttribute("class");

    // Navigate to another page
    await page.getByRole("link", { name: "トレーダー設定" }).click();
    await expect(page).toHaveURL("/traders");
    await page.waitForTimeout(500);

    const themeAfterNav = await page.locator("html").getAttribute("class");
    expect(themeAfterNav).toBe(themeAfterToggle);
  });

  test("テーマ設定がリロード後も維持される", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Switch theme
    const themeButton = page.locator("header button").filter({ has: page.locator("svg") });
    const buttons = await themeButton.all();
    for (const btn of buttons) {
      const text = await btn.textContent();
      if (!text || text.trim() === "") {
        await btn.click();
        break;
      }
    }
    await page.waitForTimeout(500);

    const themeBeforeReload = await page.locator("html").getAttribute("class");

    // Reload page
    await page.reload();
    await page.waitForLoadState("networkidle");

    const themeAfterReload = await page.locator("html").getAttribute("class");
    expect(themeAfterReload).toBe(themeBeforeReload);
  });
});
