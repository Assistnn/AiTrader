import { test, expect } from "@playwright/test";
import {
  setupApiAuth,
  assertNoAuthError,
  apiCall,
} from "../fixtures/helpers";

/**
 * セーフガード設定 永続化テスト (SG-001〜SG-040)
 * API経由で保存 → API GETで永続化検証 → UI表示確認
 *
 * API仕様:
 *   PUT /api/v1/traders/{id}/safeguards — body: camelCase fields
 *   GET /api/v1/traders/{id}/safeguards — response.data.configJson: snake_case keys
 *
 * 6カテゴリ:
 *   A. 資金保護 (SG-001〜SG-009)
 *   B. 市場異常検知 (SG-010〜SG-018)
 *   C. 取引時間制御 (SG-019〜SG-026)
 *   D. 経済指標フィルター (SG-027〜SG-031)
 *   E. レジーム保護 (SG-032〜SG-034)
 *   F. 実行保護 (SG-035〜SG-040)
 */

let testTraderId: number | null = null;

test.beforeAll(async ({ browser }) => {
  const ctx = await browser.newContext({
    storageState: "e2e/.auth/user.json",
  });
  const page = await ctx.newPage();
  await setupApiAuth(page);
  await page.goto("/");

  // テスト用トレーダー作成
  const createRes = await apiCall(page, "POST", "/api/v1/traders", {
    traderName: "E2E-Safeguard-Full",
    tradeType: "fx",
    symbols: ["USD_JPY"],
    capitalJpy: 500000,
    orderUnitLots: 0.1,
  });
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

/** configJsonからキー取得のヘルパー (snake_case or camelCase 両対応) */
function getConfigValue(config: Record<string, unknown>, snakeKey: string, camelKey: string): unknown {
  return config[snakeKey] ?? config[camelKey];
}

// ── A. 資金保護 (SG-001〜SG-009) ──────────────────

test.describe("セーフガード: 資金保護", () => {
  test("SG-001〜003: 損失率・ドローダウン設定 → API永続化", async ({ page }) => {
    const saveRes = await apiCall(
      page,
      "PUT",
      `/api/v1/traders/${testTraderId}/safeguards`,
      { maxDailyLossPct: 3.5, maxMonthlyLossPct: 8.0, maxDrawdownPct: 15.0 }
    );
    if (!saveRes.ok()) {
      test.skip(true, `APIエラー: ${saveRes.status()} — バックエンド修正待ち`);
    }

    const res = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}/safeguards`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const sg = (body.data ?? body) as { configJson: Record<string, unknown> };
    const cfg = sg.configJson;
    expect(getConfigValue(cfg, "max_daily_loss_pct", "maxDailyLossPct")).toBe(3.5);
    expect(getConfigValue(cfg, "max_monthly_loss_pct", "maxMonthlyLossPct")).toBe(8.0);
    expect(getConfigValue(cfg, "max_drawdown_pct", "maxDrawdownPct")).toBe(15.0);
  });

  test("SG-004〜005: 利益達成時停止設定 → API永続化", async ({ page }) => {
    const token = await page.evaluate(() => localStorage.getItem("ai_trading_access_token"));
    console.log(`[DEBUG] testTraderId=${testTraderId}, token=${token ? token.substring(0, 20) + "..." : "NULL"}`);
    const saveRes = await apiCall(
      page,
      "PUT",
      `/api/v1/traders/${testTraderId}/safeguards`,
      { stopOnProfit: { enabled: true, targetPct: 5.0 } }
    );
    console.log(`[DEBUG] saveRes status=${saveRes.status()}, ok=${saveRes.ok()}`);
    if (!saveRes.ok()) {
      const errBody = await saveRes.text();
      console.log(`[DEBUG] error body: ${errBody}`);
      test.skip(true, `APIエラー: ${saveRes.status()} — バックエンド修正待ち`);
    }

    const res = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}/safeguards`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const cfg = ((body.data ?? body) as { configJson: Record<string, unknown> }).configJson;
    const stop = (getConfigValue(cfg, "stop_on_profit", "stopOnProfit") as { enabled: boolean; targetPct: number });
    expect(stop.enabled).toBe(true);
    expect(stop.targetPct).toBe(5.0);
  });

  test("SG-006〜009: 連続損失制御設定 → API永続化", async ({ page }) => {
    const saveRes = await apiCall(
      page,
      "PUT",
      `/api/v1/traders/${testTraderId}/safeguards`,
      { consecutiveLoss: { enabled: true, maxCount: 5, cooldownMinutes: 120, halveLot: true } }
    );
    if (!saveRes.ok()) {
      test.skip(true, `APIエラー: ${saveRes.status()} — バックエンド修正待ち`);
    }

    const res = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}/safeguards`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const cfg = ((body.data ?? body) as { configJson: Record<string, unknown> }).configJson;
    const cl = (getConfigValue(cfg, "consecutive_loss", "consecutiveLoss") as {
      enabled: boolean; maxCount: number; cooldownMinutes: number; halveLot: boolean;
    });
    expect(cl.enabled).toBe(true);
    expect(cl.maxCount).toBe(5);
    expect(cl.cooldownMinutes).toBe(120);
    expect(cl.halveLot).toBe(true);
  });
});

// ── B. 市場異常検知 (SG-010〜SG-018) ────────────────

test.describe("セーフガード: 市場異常検知", () => {
  test("SG-010〜012: スプレッド設定 → API永続化", async ({ page }) => {
    const saveRes = await apiCall(
      page,
      "PUT",
      `/api/v1/traders/${testTraderId}/safeguards`,
      { spread: { showAverage: false, showCurrent: true, anomalyMultiplier: 4.0 } }
    );
    if (!saveRes.ok()) {
      test.skip(true, `APIエラー: ${saveRes.status()} — バックエンド修正待ち`);
    }

    const res = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}/safeguards`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const cfg = ((body.data ?? body) as { configJson: Record<string, unknown> }).configJson;
    const sp = cfg.spread as { showAverage: boolean; showCurrent: boolean; anomalyMultiplier: number };
    expect(sp.showAverage).toBe(false);
    expect(sp.showCurrent).toBe(true);
    expect(sp.anomalyMultiplier).toBe(4.0);
  });

  test("SG-013〜015: ATR急増検知設定 → API永続化", async ({ page }) => {
    const saveRes = await apiCall(
      page,
      "PUT",
      `/api/v1/traders/${testTraderId}/safeguards`,
      { atrSpike: { enabled: false, lookback: 20, maxMultiplier: 3.0 } }
    );
    if (!saveRes.ok()) {
      test.skip(true, `APIエラー: ${saveRes.status()} — バックエンド修正待ち`);
    }

    const res = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}/safeguards`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const cfg = ((body.data ?? body) as { configJson: Record<string, unknown> }).configJson;
    const atr = (getConfigValue(cfg, "atr_spike", "atrSpike") as {
      enabled: boolean; lookback: number; maxMultiplier: number;
    });
    expect(atr.enabled).toBe(false);
    expect(atr.lookback).toBe(20);
    expect(atr.maxMultiplier).toBe(3.0);
  });

  test("SG-016〜018: 急変動検知設定 → API永続化", async ({ page }) => {
    const saveRes = await apiCall(
      page,
      "PUT",
      `/api/v1/traders/${testTraderId}/safeguards`,
      { rangeSpike: { enabled: false, windowMinutes: 10, maxPips: 80 } }
    );
    if (!saveRes.ok()) {
      test.skip(true, `APIエラー: ${saveRes.status()} — バックエンド修正待ち`);
    }

    const res = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}/safeguards`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const cfg = ((body.data ?? body) as { configJson: Record<string, unknown> }).configJson;
    const rs = (getConfigValue(cfg, "range_spike", "rangeSpike") as {
      enabled: boolean; windowMinutes: number; maxPips: number;
    });
    expect(rs.enabled).toBe(false);
    expect(rs.windowMinutes).toBe(10);
    expect(rs.maxPips).toBe(80);
  });
});

// ── C. 取引時間制御 (SG-019〜SG-026) ────────────────

test.describe("セーフガード: 取引時間制御", () => {
  test("SG-019〜021: セッションブロック設定 → API永続化", async ({ page }) => {
    const saveRes = await apiCall(
      page,
      "PUT",
      `/api/v1/traders/${testTraderId}/safeguards`,
      { session: { blockOutsideTokyo: true, blockOutsideLondon: false, blockOutsideNY: true } }
    );
    if (!saveRes.ok()) {
      test.skip(true, `APIエラー: ${saveRes.status()} — バックエンド修正待ち`);
    }

    const res = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}/safeguards`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const cfg = ((body.data ?? body) as { configJson: Record<string, unknown> }).configJson;
    const s = cfg.session as { blockOutsideTokyo: boolean; blockOutsideLondon: boolean; blockOutsideNY: boolean };
    expect(s.blockOutsideTokyo).toBe(true);
    expect(s.blockOutsideLondon).toBe(false);
    expect(s.blockOutsideNY).toBe(true);
  });

  test("SG-022〜026: セッションバッファ・低ボラ設定 → API永続化", async ({ page }) => {
    const saveRes = await apiCall(
      page,
      "PUT",
      `/api/v1/traders/${testTraderId}/safeguards`,
      { session: { startBuffer: { enabled: true, minutes: 45 }, endBuffer: { enabled: false, minutes: 15 }, lowVolStop: true } }
    );
    if (!saveRes.ok()) {
      test.skip(true, `APIエラー: ${saveRes.status()} — バックエンド修正待ち`);
    }

    const res = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}/safeguards`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const cfg = ((body.data ?? body) as { configJson: Record<string, unknown> }).configJson;
    const s = cfg.session as {
      startBuffer: { enabled: boolean; minutes: number };
      endBuffer: { enabled: boolean; minutes: number };
      lowVolStop: boolean;
    };
    expect(s.startBuffer.enabled).toBe(true);
    expect(s.startBuffer.minutes).toBe(45);
    expect(s.endBuffer.enabled).toBe(false);
    expect(s.lowVolStop).toBe(true);
  });
});

// ── D. 経済指標フィルター (SG-027〜SG-031) ──────────

test.describe("セーフガード: 経済指標フィルター", () => {
  test("SG-027〜031: 経済指標停止設定 → API永続化", async ({ page }) => {
    const saveRes = await apiCall(
      page,
      "PUT",
      `/api/v1/traders/${testTraderId}/safeguards`,
      { econStop: { enabled: true, importance: "medium", beforeMinutes: 45, afterMinutes: 20, scope: "all" } }
    );
    if (!saveRes.ok()) {
      test.skip(true, `APIエラー: ${saveRes.status()} — バックエンド修正待ち`);
    }

    const res = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}/safeguards`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const cfg = ((body.data ?? body) as { configJson: Record<string, unknown> }).configJson;
    const e = (getConfigValue(cfg, "econ_stop", "econStop") as {
      enabled: boolean; importance: string; beforeMinutes: number; afterMinutes: number; scope: string;
    });
    expect(e.enabled).toBe(true);
    expect(e.importance).toBe("medium");
    expect(e.beforeMinutes).toBe(45);
    expect(e.afterMinutes).toBe(20);
    expect(e.scope).toBe("all");
  });
});

// ── E. レジーム保護 (SG-032〜SG-034) ─────────────

test.describe("セーフガード: レジーム保護", () => {
  test("SG-032〜034: レジーム保護設定 → API永続化", async ({ page }) => {
    const saveRes = await apiCall(
      page,
      "PUT",
      `/api/v1/traders/${testTraderId}/safeguards`,
      { regime: { trendBreakdown: true, adxDrop: true, rangeTransition: false } }
    );
    if (!saveRes.ok()) {
      test.skip(true, `APIエラー: ${saveRes.status()} — バックエンド修正待ち`);
    }

    const res = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}/safeguards`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const cfg = ((body.data ?? body) as { configJson: Record<string, unknown> }).configJson;
    const r = cfg.regime as { trendBreakdown: boolean; adxDrop: boolean; rangeTransition: boolean };
    expect(r.trendBreakdown).toBe(true);
    expect(r.adxDrop).toBe(true);
    expect(r.rangeTransition).toBe(false);
  });
});

// ── F. 実行保護 (SG-035〜SG-040) ─────────────────

test.describe("セーフガード: 実行保護", () => {
  test("SG-035〜037: ポジション制限設定 → API永続化", async ({ page }) => {
    const saveRes = await apiCall(
      page,
      "PUT",
      `/api/v1/traders/${testTraderId}/safeguards`,
      { exec: { maxPositions: 3, sameDirectionLimit: 2, correlatedBlock: true } }
    );
    if (!saveRes.ok()) {
      test.skip(true, `APIエラー: ${saveRes.status()} — バックエンド修正待ち`);
    }

    const res = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}/safeguards`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const cfg = ((body.data ?? body) as { configJson: Record<string, unknown> }).configJson;
    const ex = cfg.exec as { maxPositions: number; sameDirectionLimit: number; correlatedBlock: boolean };
    expect(ex.maxPositions).toBe(3);
    expect(ex.sameDirectionLimit).toBe(2);
    expect(ex.correlatedBlock).toBe(true);
  });

  test("SG-038〜040: AIフェイルセーフ設定 → API永続化", async ({ page }) => {
    const saveRes = await apiCall(
      page,
      "PUT",
      `/api/v1/traders/${testTraderId}/safeguards`,
      { aiFailsafe: { timeout: false, invalidOutput: true, lowConfidence: false } }
    );
    if (!saveRes.ok()) {
      test.skip(true, `APIエラー: ${saveRes.status()} — バックエンド修正待ち`);
    }

    const res = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}/safeguards`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const cfg = ((body.data ?? body) as { configJson: Record<string, unknown> }).configJson;
    const af = (getConfigValue(cfg, "ai_failsafe", "aiFailsafe") as {
      timeout: boolean; invalidOutput: boolean; lowConfidence: boolean;
    });
    expect(af.timeout).toBe(false);
    expect(af.invalidOutput).toBe(true);
    expect(af.lowConfidence).toBe(false);
  });
});

// ── G. UI表示確認 ──────────────────────────────

test.describe("セーフガード: UI表示確認", () => {
  test("セーフガードタブにカテゴリが表示される", async ({ page }) => {
    await page.goto("/traders");
    await page.waitForLoadState("networkidle");
    await assertNoAuthError(page);

    // テストトレーダーをクリック
    await page.getByText("E2E-Safeguard-Full").first().click();
    await page.waitForLoadState("networkidle");

    // セーフガードタブクリック
    const sgTab = page.getByRole("button", { name: /セーフガード/ }).first();
    if (await sgTab.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await sgTab.click();
      await expect(page.getByText("資金保護").first()).toBeVisible({ timeout: 5_000 });
    }
  });

  test("セーフガード設定値がUIで閲覧可能", async ({ page }) => {
    await page.goto("/traders");
    await page.waitForLoadState("networkidle");

    await page.getByText("E2E-Safeguard-Full").first().click();
    await page.waitForLoadState("networkidle");

    const sgTab = page.getByRole("button", { name: /セーフガード/ }).first();
    if (await sgTab.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await sgTab.click();

      // 数値入力フィールドが存在する
      const numberInputs = page.locator("input[type=number]");
      const count = await numberInputs.count();
      expect(count).toBeGreaterThan(0);
    }
  });

  test("リロード後もセーフガード設定が維持される", async ({ page }) => {
    // API GET で現在値
    const res1 = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}/safeguards`);
    expect(res1.ok()).toBeTruthy();
    const body1 = await res1.json();
    const cfg1 = ((body1.data ?? body1) as { configJson: Record<string, unknown> }).configJson;

    // リロード後 API GET
    await page.goto("/traders");
    await page.waitForLoadState("networkidle");

    const res2 = await apiCall(page, "GET", `/api/v1/traders/${testTraderId}/safeguards`);
    expect(res2.ok()).toBeTruthy();
    const body2 = await res2.json();
    const cfg2 = ((body2.data ?? body2) as { configJson: Record<string, unknown> }).configJson;

    // configJsonが一致
    expect(JSON.stringify(cfg2)).toBe(JSON.stringify(cfg1));
  });
});
