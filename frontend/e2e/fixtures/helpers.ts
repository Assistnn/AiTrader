import { type Page, expect } from "@playwright/test";
import fs from "fs";
import path from "path";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const AUTH_STATE_PATH = path.join(__dirname, "../.auth/user.json");

/**
 * Intercept API requests and inject Authorization header.
 * Works around the AuthGuard timing issue where apiClient.setToken()
 * runs in useEffect (after render), but SWR hooks fire during render.
 * Must be called BEFORE page.goto().
 */
export async function setupApiAuth(page: Page) {
  let token: string | undefined;
  try {
    const state = JSON.parse(fs.readFileSync(AUTH_STATE_PATH, "utf-8"));
    token = state.origins?.[0]?.localStorage?.find(
      (item: { name: string; value: string }) =>
        item.name === "ai_trading_access_token"
    )?.value;
  } catch {
    // Auth state file not found - skip
  }

  if (token) {
    await page.route("**/api/v1/**", async (route) => {
      const headers = {
        ...route.request().headers(),
        authorization: `Bearer ${token}`,
      };
      await route.fallback({ headers });
    });
  }
}

/**
 * Assert no authentication/loading error is shown on the page.
 * Call after page load to catch false positives.
 */
export async function assertNoAuthError(page: Page) {
  await expect(
    page.getByText("Not authenticated")
  ).not.toBeVisible({ timeout: 3_000 });
}

/** Wait for the page to finish loading. */
export async function waitForIdle(page: Page) {
  await page.waitForLoadState("networkidle");
}

/** Navigate and wait for domcontentloaded. */
export async function navigateTo(page: Page, urlPath: string) {
  await page.goto(urlPath);
  await page.waitForLoadState("domcontentloaded");
}

/** Direct API call bypassing the UI (useful for setup/teardown). */
export async function apiCall(
  page: Page,
  method: string,
  apiPath: string,
  body?: unknown
) {
  const token = await page.evaluate(() =>
    localStorage.getItem("ai_trading_access_token")
  );

  return page.request.fetch(`${API_BASE}${apiPath}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    data: body ? JSON.stringify(body) : undefined,
  });
}

/** Expect a toast or inline message matching text. */
export async function expectText(page: Page, text: string | RegExp) {
  await expect(page.getByText(text).first()).toBeVisible({ timeout: 5_000 });
}

/** Click a button by its visible label. */
export async function clickButton(page: Page, label: string | RegExp) {
  await page.getByRole("button", { name: label }).click();
}

/** Wait for an API response matching the given path pattern. */
export async function waitForApi(page: Page, pathPattern: string | RegExp) {
  return page.waitForResponse(
    (res) =>
      typeof pathPattern === "string"
        ? res.url().includes(pathPattern)
        : pathPattern.test(res.url()),
    { timeout: 10_000 }
  );
}
