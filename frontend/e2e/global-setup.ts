import { chromium } from "@playwright/test";
import path from "path";

const TEST_EMAIL = process.env.E2E_EMAIL ?? "test@example.com";
const TEST_PASSWORD = process.env.E2E_PASSWORD ?? "12345678";
const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";
const AUTH_FILE = path.join(__dirname, ".auth", "user.json");

async function globalSetup() {
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  await page.goto(`${BASE_URL}/login`);
  await page.getByLabel("メールアドレス").fill(TEST_EMAIL);
  await page.getByLabel("パスワード").fill(TEST_PASSWORD);
  await page.getByRole("button", { name: "ログイン" }).click();

  // Wait for redirect to dashboard
  await page.waitForURL(`${BASE_URL}/`, { timeout: 10_000 });

  // Save auth state
  await context.storageState({ path: AUTH_FILE });

  await browser.close();
}

export default globalSetup;
