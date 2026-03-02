import { chromium } from "@playwright/test";
import path from "path";
import fs from "fs";

const TEST_EMAIL = process.env.E2E_EMAIL ?? "test@example.com";
const TEST_PASSWORD = process.env.E2E_PASSWORD ?? "12345678";
const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";
const AUTH_FILE = path.join(__dirname, ".auth", "user.json");

async function globalSetup() {
  // 既存auth stateが有効ならスキップ
  if (fs.existsSync(AUTH_FILE)) {
    try {
      const state = JSON.parse(fs.readFileSync(AUTH_FILE, "utf-8"));
      const token = state.origins?.[0]?.localStorage?.find(
        (item: { name: string; value: string }) =>
          item.name === "ai_trading_access_token"
      )?.value;
      if (token) {
        // JWTのexp確認（base64デコード）
        const payload = JSON.parse(
          Buffer.from(token.split(".")[1], "base64url").toString()
        );
        if (payload.exp && payload.exp * 1000 > Date.now()) {
          console.log("Auth state is valid, skipping login");
          return;
        }
      }
    } catch {
      // パース失敗時はログインを実行
    }
  }

  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  await page.goto(`${BASE_URL}/login`);
  await page.getByLabel("メールアドレス").fill(TEST_EMAIL);
  await page.getByLabel("パスワード").fill(TEST_PASSWORD);
  await page.getByRole("button", { name: "ログイン" }).click();

  // Wait for redirect to dashboard (or stay on login with token set)
  await page.waitForURL((url) => !url.pathname.includes("/login"), { timeout: 15_000 })
    .catch(() => {
      // ログイン後リダイレクトしない場合でもauth stateは保存されている可能性
    });

  // Save auth state
  await context.storageState({ path: AUTH_FILE });

  await browser.close();
}

export default globalSetup;
