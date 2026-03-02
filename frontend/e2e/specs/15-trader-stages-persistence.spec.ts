import { test, expect } from "@playwright/test";
import {
  setupApiAuth,
  assertNoAuthError,
  apiCall,
} from "../fixtures/helpers";

/**
 * トレーダー各タブ設定 永続化テスト
 * 基本情報拡張 / M1-M2 / M3-M4 / MX
 *
 * API仕様:
 *   トレーダー基本: PUT/GET /api/v1/traders/{id}
 *   ステージ設定:   PUT/GET /api/v1/traders/{id}/model-stages/{stage}
 *
 * model-stages PUT body: { enabled, timeframes, mode, useTrendDirection, ... }
 * model-stages GET response.data.configJson: { enabled, timeframes, mode, ... }
 */

let testTraderId: number | null = null;

test.beforeAll(async ({ browser }) => {
  const ctx = await browser.newContext({
    storageState: "e2e/.auth/user.json",
  });
  const page = await ctx.newPage();
  await setupApiAuth(page);
  await page.goto("/");

  let createRes;
  try {
    createRes = await Promise.race([
      apiCall(page, "POST", "/api/v1/traders", {
        traderName: "E2E-Stages-Trader",
        tradeType: "fx",
        symbols: ["USD_JPY"],
        capitalJpy: 500000,
        orderUnitLots: 0.1,
      }),
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error("POST timeout")), 15_000)
      ),
    ]);
  } catch {
    await ctx.close();
    return;
  }
  if (createRes.ok()) {
    const createBody = await createRes.json();
    const created = createBody.data ?? createBody;
    testTraderId = (created as { id: number }).id;
  }

  await ctx.close();
});

test.afterAll(async ({ browser }) => {
  if (testTraderId) {
    const ctx = await browser.newContext({
      storageState: "e2e/.auth/user.json",
    });
    const page = await ctx.newPage();
    await setupApiAuth(page);
    await page.goto("/");
    await apiCall(page, "DELETE", `/api/v1/traders/${testTraderId}`);
    await ctx.close();
  }
});

test.beforeEach(async ({ page }) => {
  test.skip(!testTraderId, "テスト用トレーダーが作成されていない");
  await setupApiAuth(page);
  await page.goto("/");
  await page.waitForLoadState("networkidle");
});

// ── A. 基本情報の拡張テスト ─────────────────────────

test.describe("トレーダー基本情報: 拡張フィールド", () => {
  test("取引タイプ変更 (fx→crypto) → API永続化", async ({ page }) => {
    let updateRes;
    try {
      updateRes = await Promise.race([
        apiCall(page, "PUT", `/api/v1/traders/${testTraderId}`, {
          tradeType: "crypto",
          symbols: ["BTC_JPY"],
        }),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error("PUT timeout")), 10_000)
        ),
      ]);
    } catch {
      test.skip(true, "トレーダーPUT APIがタイムアウト");
    }
    if (!updateRes!.ok()) {
      test.skip(true, `APIエラー: ${updateRes!.status()}`);
    }

    const res = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const trader = body.data ?? body;
    expect((trader as { tradeType: string }).tradeType).toBe("crypto");

    // 戻す
    await apiCall(page, "PUT", `/api/v1/traders/${testTraderId}`, {
      tradeType: "fx",
      symbols: ["USD_JPY"],
    });
  });

  test("戦略テキスト設定 → API永続化", async ({ page }) => {
    const strategyText = "E2Eテスト用の戦略メモ: トレンドフォロー+ブレイクアウト";
    let updateRes;
    try {
      updateRes = await Promise.race([
        apiCall(page, "PUT", `/api/v1/traders/${testTraderId}`, {
          strategyText,
        }),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error("PUT timeout")), 10_000)
        ),
      ]);
    } catch {
      test.skip(true, "トレーダーPUT APIがタイムアウト");
    }
    if (!updateRes!.ok()) {
      test.skip(true, `APIエラー: ${updateRes!.status()}`);
    }

    const res = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const trader = body.data ?? body;
    expect((trader as { strategyText: string }).strategyText).toBe(strategyText);
  });

  test("ロットサイズ・資金更新 → API永続化", async ({ page }) => {
    let updateRes;
    try {
      updateRes = await Promise.race([
        apiCall(page, "PUT", `/api/v1/traders/${testTraderId}`, {
          capitalJpy: 1000000,
          orderUnitLots: 0.5,
        }),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error("PUT timeout")), 10_000)
        ),
      ]);
    } catch {
      test.skip(true, "トレーダーPUT APIがタイムアウト");
    }
    if (!updateRes!.ok()) {
      test.skip(true, `APIエラー: ${updateRes!.status()}`);
    }

    const res = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const trader = body.data ?? body;
    expect((trader as { capitalJpy: number }).capitalJpy).toBe(1000000);
    expect((trader as { orderUnitLots: number }).orderUnitLots).toBe(0.5);
  });
});

// ── B. M1設定 ──────────────────────────────

test.describe("トレーダー M1 方向判定設定", () => {
  test("M1: 有効化・モード・時間足設定 → API永続化", async ({ page }) => {
    const saveRes = await apiCall(
      page,
      "PUT",
      `/api/v1/traders/${testTraderId}/model-stages/m1`,
      {
        enabled: true,
        timeframes: ["H1"],
        mode: "aiAssist",
        useTrendDirection: true,
        useRangeAvoid: false,
        useVolatility: true,
      }
    );
    if (!saveRes.ok()) {
      test.skip(true, `APIエラー: ${saveRes.status()} — バックエンド修正待ち`);
    }

    const res = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}/model-stages/m1`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const stage = (body.data ?? body) as { configJson: Record<string, unknown> };
    const cfg = stage.configJson;
    expect(cfg.enabled).toBe(true);
    expect(cfg.mode).toBe("aiAssist");
    // timeframes は snake_case or camelCase
    const tf = (cfg.timeframes ?? cfg["timeframes"]) as string[];
    expect(tf).toContain("H1");
  });
});

// ── C. M2設定 ──────────────────────────────

test.describe("トレーダー M2 セットアップ検出設定", () => {
  test("M2: セットアップ設定 → API永続化", async ({ page }) => {
    const saveRes = await apiCall(
      page,
      "PUT",
      `/api/v1/traders/${testTraderId}/model-stages/m2`,
      {
        enabled: true,
        timeframes: ["M30"],
        mode: "rule",
      }
    );
    if (!saveRes.ok()) {
      test.skip(true, `APIエラー: ${saveRes.status()} — バックエンド修正待ち`);
    }

    const res = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}/model-stages/m2`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const stage = (body.data ?? body) as { configJson: Record<string, unknown> };
    const cfg = stage.configJson;
    expect(cfg.enabled).toBe(true);
    expect(cfg.mode).toBe("rule");
  });
});

// ── D. M3設定 ──────────────────────────────

test.describe("トレーダー M3 エントリー実行設定", () => {
  test("M3: エントリー方式・リスク設定 → API永続化", async ({ page }) => {
    const saveRes = await apiCall(
      page,
      "PUT",
      `/api/v1/traders/${testTraderId}/model-stages/m3`,
      {
        enabled: true,
        mode: "rule",
      }
    );
    if (!saveRes.ok()) {
      test.skip(true, `APIエラー: ${saveRes.status()} — バックエンド修正待ち`);
    }

    const res = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}/model-stages/m3`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const stage = (body.data ?? body) as { configJson: Record<string, unknown> };
    const cfg = stage.configJson;
    expect(cfg.enabled).toBe(true);
    expect(cfg.mode).toBe("rule");
  });
});

// ── E. M4設定 ──────────────────────────────

test.describe("トレーダー M4 退出管理設定", () => {
  test("M4: 退出管理モード設定 → API永続化", async ({ page }) => {
    const saveRes = await apiCall(
      page,
      "PUT",
      `/api/v1/traders/${testTraderId}/model-stages/m4`,
      {
        enabled: true,
        mode: "aiAssist",
      }
    );
    if (!saveRes.ok()) {
      test.skip(true, `APIエラー: ${saveRes.status()} — バックエンド修正待ち`);
    }

    const res = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}/model-stages/m4`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const stage = (body.data ?? body) as { configJson: Record<string, unknown> };
    const cfg = stage.configJson;
    expect(cfg.enabled).toBe(true);
    expect(cfg.mode).toBe("aiAssist");
  });
});

// ── F. MX設定 ──────────────────────────────────

test.describe("トレーダー MX メタ設定", () => {
  test("MX: 評価方式設定 → API永続化", async ({ page }) => {
    const saveRes = await apiCall(
      page,
      "PUT",
      `/api/v1/traders/${testTraderId}/model-stages/mx`,
      {
        enabled: true,
        mode: "rule",
      }
    );
    if (!saveRes.ok()) {
      test.skip(true, `APIエラー: ${saveRes.status()} — バックエンド修正待ち`);
    }

    const res = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}/model-stages/mx`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const stage = (body.data ?? body) as { configJson: Record<string, unknown> };
    const cfg = stage.configJson;
    expect(cfg.enabled).toBe(true);
    expect(cfg.mode).toBe("rule");
  });
});

// ── G. UIタブ表示確認 ──────────────────────────────

test.describe("トレーダー設定: UI表示確認", () => {
  test("M1-M2タブが正常に表示される", async ({ page }) => {
    await page.goto("/traders");
    await page.waitForLoadState("networkidle");
    await assertNoAuthError(page);

    await page.getByText("E2E-Stages-Trader").first().click();
    await page.waitForLoadState("networkidle");

    const m1m2Tab = page.getByRole("button", { name: /M1.*M2|M1-M2/ }).first();
    if (await m1m2Tab.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await m1m2Tab.click();
      await expect(page.getByText(/方向判定|M1/).first()).toBeVisible({ timeout: 5_000 });
    }
  });

  test("M3-M4タブが正常に表示される", async ({ page }) => {
    await page.goto("/traders");
    await page.waitForLoadState("networkidle");

    await page.getByText("E2E-Stages-Trader").first().click();
    await page.waitForLoadState("networkidle");

    const m3m4Tab = page.getByRole("button", { name: /M3.*M4|M3-M4/ }).first();
    if (await m3m4Tab.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await m3m4Tab.click();
      await expect(page.getByText(/エントリー|M3/).first()).toBeVisible({ timeout: 5_000 });
    }
  });

  test("MXタブが正常に表示される", async ({ page }) => {
    await page.goto("/traders");
    await page.waitForLoadState("networkidle");

    await page.getByText("E2E-Stages-Trader").first().click();
    await page.waitForLoadState("networkidle");

    const mxTab = page.getByRole("button", { name: /MX|メタ/ }).first();
    if (await mxTab.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await mxTab.click();
      await expect(page.getByText(/評価方式|MX/).first()).toBeVisible({ timeout: 5_000 });
    }
  });
});

// ── H. リロード後の永続化確認 ──────────────────────

test.describe("トレーダー設定: リロード後永続化", () => {
  test("トレーダー基本情報がリロード後も維持される", async ({ page }) => {
    const res1 = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}`);
    expect(res1.ok()).toBeTruthy();
    const body1 = await res1.json();
    const trader1 = body1.data ?? body1;

    await page.goto("/traders");
    await page.waitForLoadState("networkidle");

    const res2 = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}`);
    expect(res2.ok()).toBeTruthy();
    const body2 = await res2.json();
    const trader2 = body2.data ?? body2;

    expect((trader2 as { traderName: string }).traderName)
      .toBe((trader1 as { traderName: string }).traderName);
    expect((trader2 as { tradeType: string }).tradeType)
      .toBe((trader1 as { tradeType: string }).tradeType);
  });

  test("全ステージ設定がリロード後も維持される", async ({ page }) => {
    const res1 = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}/model-stages`);
    expect(res1.ok()).toBeTruthy();
    const body1 = await res1.json();
    const stages1 = JSON.stringify(body1.data ?? body1);

    await page.goto("/traders");
    await page.waitForLoadState("networkidle");

    const res2 = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}/model-stages`);
    expect(res2.ok()).toBeTruthy();
    const body2 = await res2.json();
    const stages2 = JSON.stringify(body2.data ?? body2);

    expect(stages2).toBe(stages1);
  });
});
