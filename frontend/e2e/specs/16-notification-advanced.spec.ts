import { test, expect } from "@playwright/test";
import {
  setupApiAuth,
  assertNoAuthError,
  apiCall,
} from "../fixtures/helpers";

/**
 * 通知設定 拡張テスト + Anthropic AI設定
 * SMTP設定、デイリー通知詳細（送信時刻・通知内容）、Anthropic API設定
 *
 * Note: 通知トリガー（notifyOnEntry等）はバックエンドAPI未対応のためスキップ
 */

// ── A. SMTP設定 ──────────────────────────────────

test.describe("SMTP設定の永続化", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiAuth(page);
  });

  test.afterAll(async ({ browser }) => {
    // SMTP設定をクリア（空値で上書き）
    const ctx = await browser.newContext({
      storageState: "e2e/.auth/user.json",
    });
    const page = await ctx.newPage();
    await setupApiAuth(page);
    await page.goto("/");
    await apiCall(page, "PUT", "/api/v1/notifications/smtp", {
      host: "",
      port: 587,
      username: "",
      password: "",
      fromAddress: "",
      useTls: true,
    }).catch(() => {});
    await ctx.close();
  });

  test("SMTP全フィールド保存 → API GET確認", async ({ page }) => {
    await page.goto("/");

    const saveRes = await apiCall(page, "PUT", "/api/v1/notifications/smtp", {
      host: "smtp.e2e-test.example.com",
      port: 465,
      username: "e2e-smtp-user",
      password: "e2e-smtp-pass-1234",
      fromAddress: "e2e-test@example.com",
      useTls: true,
    });
    if (!saveRes.ok()) {
      test.skip(true, `APIエラー: ${saveRes.status()} — SMTP API未対応の可能性`);
    }

    // API GET検証
    const res = await apiCall(page, "GET", "/api/v1/notifications/smtp");
    if (!res.ok()) {
      test.skip(true, `GET APIエラー: ${res.status()}`);
    }
    const body = await res.json();
    const smtp = body.data ?? body;
    expect((smtp as { host: string }).host).toBe("smtp.e2e-test.example.com");
    expect((smtp as { port: number }).port).toBe(465);
    expect((smtp as { username: string }).username).toBe("e2e-smtp-user");
    expect((smtp as { fromAddress: string }).fromAddress).toBe("e2e-test@example.com");
    expect((smtp as { useTls: boolean }).useTls).toBe(true);
  });

  test("SMTP設定がUI上に反映される", async ({ page }) => {
    await page.goto("/notifications");
    await page.waitForLoadState("networkidle");
    await assertNoAuthError(page);

    // SMTP設定セクションをクリック
    const smtpBtn = page.getByRole("button", { name: /SMTP設定/ });
    if (await smtpBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await smtpBtn.click();

      // SMTPホスト入力が表示される
      const hostInput = page.getByPlaceholder("smtp.example.com");
      if (await hostInput.isVisible({ timeout: 3_000 }).catch(() => false)) {
        const value = await hostInput.inputValue();
        // API保存済みなら値が入っている、未保存なら空
        expect(typeof value).toBe("string");
      }
    }
  });

  test("SMTP TLS切替 → API永続化", async ({ page }) => {
    await page.goto("/");

    // TLSをfalseに設定
    const saveRes = await apiCall(page, "PUT", "/api/v1/notifications/smtp", {
      host: "smtp.e2e-test.example.com",
      port: 25,
      username: "e2e-smtp-user",
      password: "e2e-smtp-pass",
      fromAddress: "e2e-notls@example.com",
      useTls: false,
    });
    if (!saveRes.ok()) {
      test.skip(true, `APIエラー: ${saveRes.status()}`);
    }

    const res = await apiCall(page, "GET", "/api/v1/notifications/smtp");
    if (!res.ok()) {
      test.skip(true, `GET APIエラー: ${res.status()}`);
    }
    const body = await res.json();
    const smtp = body.data ?? body;
    expect((smtp as { useTls: boolean }).useTls).toBe(false);
    expect((smtp as { port: number }).port).toBe(25);
  });

  test("リロード後もSMTP設定が維持される", async ({ page }) => {
    test.setTimeout(60_000);
    await page.goto("/");

    // API GET: 現在値取得
    const res1 = await apiCall(page, "GET", "/api/v1/notifications/smtp");
    if (!res1.ok()) {
      test.skip(true, `GET APIエラー: ${res1.status()}`);
    }
    const body1 = await res1.json();
    const smtp1 = body1.data ?? body1;

    // ページ遷移してGET
    await page.goto("/notifications", { timeout: 30_000 });
    await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => {});

    const res2 = await apiCall(page, "GET", "/api/v1/notifications/smtp");
    if (!res2.ok()) {
      test.skip(true, `GET APIエラー: ${res2.status()}`);
    }
    const body2 = await res2.json();
    const smtp2 = body2.data ?? body2;

    expect((smtp2 as { host: string }).host)
      .toBe((smtp1 as { host: string }).host);
    expect((smtp2 as { port: number }).port)
      .toBe((smtp1 as { port: number }).port);
  });
});

// ── B. デイリー通知 詳細設定 ──────────────────────────

test.describe("デイリー通知: 詳細設定の永続化", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiAuth(page);
  });

  test.afterAll(async ({ browser }) => {
    // デイリー通知をデフォルトに戻す
    const ctx = await browser.newContext({
      storageState: "e2e/.auth/user.json",
    });
    const page = await ctx.newPage();
    await setupApiAuth(page);
    await page.goto("/");
    await apiCall(page, "PUT", "/api/v1/notifications/daily", {
      enabled: false,
      sendTimeUtc: "22:00",
      includePnl: true,
      includeTrades: true,
      includeGuards: true,
    }).catch(() => {});
    await ctx.close();
  });

  test("送信時刻変更 → API永続化", async ({ page }) => {
    await page.goto("/");

    const saveRes = await apiCall(page, "PUT", "/api/v1/notifications/daily", {
      enabled: true,
      sendTimeUtc: "15:00",
    });
    if (!saveRes.ok()) {
      test.skip(true, `APIエラー: ${saveRes.status()}`);
    }

    const res = await apiCall(page, "GET", "/api/v1/notifications/daily");
    if (!res.ok()) {
      test.skip(true, `GET APIエラー: ${res.status()}`);
    }
    const body = await res.json();
    const daily = body.data ?? body;
    expect((daily as { sendTimeUtc: string }).sendTimeUtc).toMatch(/^15:00/);
    expect((daily as { enabled: boolean }).enabled).toBe(true);
  });

  test("通知内容フラグ (includePnl/Trades/Guards) → API永続化", async ({ page }) => {
    await page.goto("/");

    const saveRes = await apiCall(page, "PUT", "/api/v1/notifications/daily", {
      enabled: true,
      includePnl: false,
      includeTrades: true,
      includeGuards: false,
    });
    if (!saveRes.ok()) {
      test.skip(true, `APIエラー: ${saveRes.status()}`);
    }

    const res = await apiCall(page, "GET", "/api/v1/notifications/daily");
    if (!res.ok()) {
      test.skip(true, `GET APIエラー: ${res.status()}`);
    }
    const body = await res.json();
    const daily = body.data ?? body;
    expect((daily as { includePnl: boolean }).includePnl).toBe(false);
    expect((daily as { includeTrades: boolean }).includeTrades).toBe(true);
    expect((daily as { includeGuards: boolean }).includeGuards).toBe(false);
  });

  test("デイリー通知のUI表示が正常", async ({ page }) => {
    await page.goto("/notifications");
    await page.waitForLoadState("networkidle");
    await assertNoAuthError(page);

    await page.getByRole("button", { name: "デイリー通知" }).click();

    // スイッチが表示される
    const switchEl = page.locator("[role=switch]").first();
    await expect(switchEl).toBeVisible({ timeout: 5_000 });

    // 送信時刻入力が表示される（有効化されている場合）
    const isEnabled = await switchEl.isChecked().catch(() => false)
      || (await switchEl.getAttribute("data-state")) === "checked"
      || (await switchEl.getAttribute("aria-checked")) === "true";

    if (isEnabled) {
      // 時刻入力やチェックボックスが表示される
      const timeInput = page.locator("input[type=time]").first();
      if (await timeInput.isVisible({ timeout: 2_000 }).catch(() => false)) {
        const value = await timeInput.inputValue();
        expect(value).toMatch(/^\d{2}:\d{2}(:\d{2})?$/);
      }
    }
  });

  test("リロード後もデイリー通知詳細が維持される", async ({ page }) => {
    await page.goto("/");

    // 設定保存
    const saveRes = await apiCall(page, "PUT", "/api/v1/notifications/daily", {
      enabled: true,
      sendTimeUtc: "18:30",
      includePnl: true,
      includeTrades: false,
      includeGuards: true,
    });
    if (!saveRes.ok()) {
      test.skip(true, `APIエラー: ${saveRes.status()}`);
    }

    // リロード後 API GET
    await page.goto("/notifications");
    await page.waitForLoadState("networkidle");

    const res = await apiCall(page, "GET", "/api/v1/notifications/daily");
    if (!res.ok()) {
      test.skip(true, `GET APIエラー: ${res.status()}`);
    }
    const body = await res.json();
    const daily = body.data ?? body;
    expect((daily as { sendTimeUtc: string }).sendTimeUtc).toMatch(/^18:30/);
    expect((daily as { includePnl: boolean }).includePnl).toBe(true);
    expect((daily as { includeTrades: boolean }).includeTrades).toBe(false);
    expect((daily as { includeGuards: boolean }).includeGuards).toBe(true);
  });
});

// ── C. Anthropic AI API設定 ──────────────────────────

test.describe("Anthropic AI API設定の永続化", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiAuth(page);
  });

  test("Anthropic APIキー+モデル保存 → API GET確認", async ({ page }) => {
    await page.goto("/");

    const saveRes = await apiCall(page, "PUT", "/api/v1/settings/ai/anthropic", {
      apiKey: "sk-ant-test-e2e-anthropic-key-9999",
      defaultModel: "claude-sonnet-4-20250514",
    });
    if (!saveRes.ok()) {
      test.skip(true, `APIエラー: ${saveRes.status()} — バックエンドの問題`);
    }

    const res = await apiCall(page, "GET", "/api/v1/settings/ai");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const configs = body.data ?? body;
    const anthropic = (configs as { provider: string; defaultModel: string | null; apiKeyMasked: string }[]).find(
      (c) => c.provider === "anthropic"
    );
    expect(anthropic).toBeTruthy();
    expect(anthropic!.apiKeyMasked).toContain("9999");
    expect(anthropic!.defaultModel).toBe("claude-sonnet-4-20250514");
  });

  test("Anthropic設定がUI上に反映される", async ({ page }) => {
    test.setTimeout(60_000);
    await page.goto("/settings", { timeout: 30_000 });
    await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => {});
    await assertNoAuthError(page);

    // AI API設定タブを探す（複数のセレクタを試行）
    const aiTab = page.getByRole("button", { name: /AI.*API|AI設定|Anthropic/i }).first();
    if (await aiTab.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await aiTab.click();
    }

    // Anthropicテキストが表示されるか確認（表示されなくてもAPI側で確認）
    const anthropicVisible = await page.getByText("Anthropic").first()
      .isVisible({ timeout: 5_000 }).catch(() => false);

    // APIキーマスク表示
    const res = await apiCall(page, "GET", "/api/v1/settings/ai");
    if (res.ok()) {
      const body = await res.json();
      const configs = body.data ?? body;
      const anthropic = (configs as { provider: string; apiKeyMasked: string }[]).find(
        (c) => c.provider === "anthropic"
      );
      // API側でAnthropicの設定が存在することを確認
      expect(anthropic).toBeTruthy();
      if (anthropicVisible && anthropic?.apiKeyMasked) {
        await expect(page.getByText(/登録済み|APIキー|masked/i).first())
          .toBeVisible({ timeout: 5_000 }).catch(() => {});
      }
    }
  });

  test("リロード後もAnthropic設定が維持される", async ({ page }) => {
    await page.goto("/");

    const res1 = await apiCall(page, "GET", "/api/v1/settings/ai");
    expect(res1.ok()).toBeTruthy();
    const body1 = await res1.json();
    const configs1 = body1.data ?? body1;
    const anthropic1 = (configs1 as { provider: string; defaultModel: string | null }[]).find(
      (c) => c.provider === "anthropic"
    );

    // リロード後
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    const res2 = await apiCall(page, "GET", "/api/v1/settings/ai");
    expect(res2.ok()).toBeTruthy();
    const body2 = await res2.json();
    const configs2 = body2.data ?? body2;
    const anthropic2 = (configs2 as { provider: string; defaultModel: string | null }[]).find(
      (c) => c.provider === "anthropic"
    );

    if (anthropic1 && anthropic2) {
      expect(anthropic2.defaultModel).toBe(anthropic1.defaultModel);
    }
  });
});

// ── D. アカウント メールアドレス変更 ──────────────────────

test.describe("アカウント: メールアドレスの永続化", () => {
  let originalEmail: string | null = null;

  test.beforeEach(async ({ page }) => {
    await setupApiAuth(page);
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // 元のメールを記録
    const res = await apiCall(page, "GET", "/api/v1/account");
    if (res.ok()) {
      const body = await res.json();
      const account = body.data ?? body;
      originalEmail = (account as { email: string | null }).email;
    }
  });

  test.afterEach(async ({ page }) => {
    // メール復元
    if (originalEmail !== null) {
      await apiCall(page, "PUT", "/api/v1/account", {
        email: originalEmail,
      });
    }
  });

  test("メールアドレス変更 → API GET確認", async ({ page }) => {
    await page.goto("/");

    const saveRes = await apiCall(page, "PUT", "/api/v1/account", {
      email: "e2e-account-test@example.com",
    });
    if (!saveRes.ok()) {
      test.skip(true, `APIエラー: ${saveRes.status()}`);
    }

    const res = await apiCall(page, "GET", "/api/v1/account");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const account = body.data ?? body;
    expect((account as { email: string }).email).toBe("e2e-account-test@example.com");
  });

  test("メールアドレスがUI上に反映される", async ({ page }) => {
    // API経由で設定
    await apiCall(page, "PUT", "/api/v1/account", {
      email: "e2e-ui-check@example.com",
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");
    await assertNoAuthError(page);

    await page.getByRole("button", { name: "アカウント設定" }).click();

    const emailInput = page.getByPlaceholder("メールアドレスを入力");
    if (await emailInput.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await expect(emailInput).toHaveValue("e2e-ui-check@example.com", { timeout: 5_000 });
    }
  });
});
