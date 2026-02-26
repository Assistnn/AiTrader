"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import useSWR from "swr";
import { Header } from "@/components/common/Header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { apiClient, fetcher } from "@/lib/api";
import { Select } from "@/components/ui/select";
import { SafeguardSettingsPanel } from "@/components/dashboard/SafeguardSettingsPanel";
import { useTraders } from "@/hooks/useDashboard";
import type {
  ExchangeConfig,
  AiConfig,
  AccountInfo,
  CostConfig,
} from "@/types/api";

type SettingsSection =
  | "exchange"
  | "ai"
  | "safeguard"
  | "cost"
  | "account";

const sections: { key: SettingsSection; label: string }[] = [
  { key: "exchange", label: "取引所API設定" },
  { key: "ai", label: "AI API設定" },
  { key: "safeguard", label: "セーフガード設定" },
  { key: "cost", label: "コスト管理" },
  { key: "account", label: "アカウント設定" },
];

const subLinks = [
  { href: "/backtests", label: "バックテスト" },
  { href: "/pipeline-logs", label: "パイプラインログ" },
  { href: "/config-changes", label: "設定変更履歴" },
];

/* ================================================================
 * Exchange Settings
 * GET /api/v1/settings/exchanges
 * PUT /api/v1/settings/exchanges/{exchangeType}
 * ================================================================ */
function ExchangeSettings() {
  const { data: configs, mutate } = useSWR<ExchangeConfig[]>(
    "/api/v1/settings/exchanges",
    fetcher
  );
  const [saving, setSaving] = useState<string | null>(null);
  const [forms, setForms] = useState<
    Record<string, { apiKey: string; apiSecret: string }>
  >({
    gmo: { apiKey: "", apiSecret: "" },
    bitbank: { apiKey: "", apiSecret: "" },
  });

  const exchanges = [
    { type: "gmo", label: "GMOコイン" },
    { type: "bitbank", label: "bitbank" },
  ];

  const getMasked = (type: string) =>
    configs?.find((c) => c.exchangeType === type)?.apiKeyMasked;

  const handleSave = async (type: string) => {
    const form = forms[type];
    if (!form.apiKey || !form.apiSecret) return;
    setSaving(type);
    try {
      await apiClient.put(`/api/v1/settings/exchanges/${type}`, {
        apiKey: form.apiKey,
        apiSecret: form.apiSecret,
      });
      setForms((prev) => ({
        ...prev,
        [type]: { apiKey: "", apiSecret: "" },
      }));
      await mutate();
    } catch {
      // Error handled by apiClient
    } finally {
      setSaving(null);
    }
  };

  return (
    <div className="space-y-6">
      {exchanges.map((ex, idx) => (
        <div key={ex.type} className="space-y-3">
          <h4 className="text-sm font-semibold">{ex.label}</h4>
          {getMasked(ex.type) && (
            <p className="text-xs text-muted-foreground">
              登録済みAPIキー: {getMasked(ex.type)}
            </p>
          )}
          <div>
            <label className="text-sm font-medium">APIキー</label>
            <Input
              type="password"
              placeholder="新しいAPIキーを入力"
              value={forms[ex.type].apiKey}
              onChange={(e) =>
                setForms((prev) => ({
                  ...prev,
                  [ex.type]: { ...prev[ex.type], apiKey: e.target.value },
                }))
              }
            />
          </div>
          <div>
            <label className="text-sm font-medium">シークレットキー</label>
            <Input
              type="password"
              placeholder="新しいシークレットキーを入力"
              value={forms[ex.type].apiSecret}
              onChange={(e) =>
                setForms((prev) => ({
                  ...prev,
                  [ex.type]: { ...prev[ex.type], apiSecret: e.target.value },
                }))
              }
            />
          </div>
          <Button
            onClick={() => handleSave(ex.type)}
            disabled={
              saving !== null ||
              !forms[ex.type].apiKey ||
              !forms[ex.type].apiSecret
            }
          >
            {saving === ex.type ? "保存中..." : "保存"}
          </Button>
          {idx < exchanges.length - 1 && <hr className="my-2" />}
        </div>
      ))}
    </div>
  );
}

/* ================================================================
 * AI Settings
 * GET /api/v1/settings/ai
 * PUT /api/v1/settings/ai/{provider}
 * ================================================================ */
function AISettings() {
  const { data: configs, mutate } = useSWR<AiConfig[]>(
    "/api/v1/settings/ai",
    fetcher
  );
  const [saving, setSaving] = useState<string | null>(null);
  const [forms, setForms] = useState<
    Record<string, { apiKey: string; defaultModel: string }>
  >({
    openai: { apiKey: "", defaultModel: "" },
    gemini: { apiKey: "", defaultModel: "" },
    anthropic: { apiKey: "", defaultModel: "" },
  });

  const providers = [
    { name: "openai", label: "OpenAI", placeholder: "sk-..." },
    { name: "gemini", label: "Google Gemini", placeholder: "AIza..." },
    { name: "anthropic", label: "Anthropic", placeholder: "sk-ant-..." },
  ];

  const getConfig = (provider: string) =>
    configs?.find((c) => c.provider === provider);

  const handleSave = async (provider: string) => {
    const form = forms[provider];
    if (!form.apiKey) return;
    setSaving(provider);
    try {
      await apiClient.put(`/api/v1/settings/ai/${provider}`, {
        apiKey: form.apiKey,
        ...(form.defaultModel ? { defaultModel: form.defaultModel } : {}),
      });
      setForms((prev) => ({
        ...prev,
        [provider]: { apiKey: "", defaultModel: "" },
      }));
      await mutate();
    } catch {
      // Error handled by apiClient
    } finally {
      setSaving(null);
    }
  };

  return (
    <div className="space-y-6">
      {providers.map((p, idx) => {
        const existing = getConfig(p.name);
        return (
          <div key={p.name} className="space-y-3">
            <h4 className="text-sm font-semibold">{p.label}</h4>
            {existing && (
              <p className="text-xs text-muted-foreground">
                登録済みAPIキー: {existing.apiKeyMasked}
                {existing.defaultModel &&
                  ` / モデル: ${existing.defaultModel}`}
              </p>
            )}
            <div>
              <label className="text-sm font-medium">APIキー</label>
              <Input
                type="password"
                placeholder={p.placeholder}
                value={forms[p.name].apiKey}
                onChange={(e) =>
                  setForms((prev) => ({
                    ...prev,
                    [p.name]: { ...prev[p.name], apiKey: e.target.value },
                  }))
                }
              />
            </div>
            <div>
              <label className="text-sm font-medium">デフォルトモデル</label>
              <Input
                placeholder={existing?.defaultModel || "未設定"}
                value={forms[p.name].defaultModel}
                onChange={(e) =>
                  setForms((prev) => ({
                    ...prev,
                    [p.name]: {
                      ...prev[p.name],
                      defaultModel: e.target.value,
                    },
                  }))
                }
              />
            </div>
            <Button
              onClick={() => handleSave(p.name)}
              disabled={saving !== null || !forms[p.name].apiKey}
            >
              {saving === p.name ? "保存中..." : "保存"}
            </Button>
            {idx < providers.length - 1 && <hr className="my-2" />}
          </div>
        );
      })}
    </div>
  );
}

/* ================================================================
 * Safeguard Settings (placeholder — Phase B implementation)
 * ================================================================ */
function SafeguardSettings() {
  const { data: traders } = useTraders();
  const [traderId, setTraderId] = useState<number | null>(null);

  // Auto-select first trader
  useEffect(() => {
    if (traders && traders.length > 0 && traderId === null) {
      setTraderId(traders[0].id);
    }
  }, [traders, traderId]);

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        セーフガードルール（SG-001 ~ SG-040）をトレーダーごとに設定します。
      </p>
      <div>
        <label className="text-xs font-medium">トレーダー選択</label>
        <Select
          value={traderId ? String(traderId) : ""}
          options={
            traders?.map((t) => ({
              value: String(t.id),
              label: t.traderName,
            })) || []
          }
          onChange={(e) => setTraderId(Number(e.target.value))}
        />
      </div>
      {traderId && <SafeguardSettingsPanel traderId={traderId} />}
    </div>
  );
}

/* ================================================================
 * Cost Settings (read-only from server config)
 * GET /api/v1/settings/cost
 * Reference: 14_コスト管理
 * ================================================================ */
function CostSettings() {
  const { data: config } = useSWR<CostConfig>(
    "/api/v1/settings/cost",
    fetcher
  );

  const items = [
    {
      label: "日次トークン上限",
      value: config?.dailyTokenLimit ?? 1_000_000,
      unit: "tokens",
      description:
        "日次トークン使用量がこの上限を超えるとAI呼び出しが停止します",
    },
    {
      label: "レートリミット（トレーダー/分）",
      value: config?.rateLimitPerTrader ?? 10,
      unit: "回/分",
      description: "",
    },
    {
      label: "グローバルレートリミット（/分）",
      value: config?.rateLimitGlobal ?? 30,
      unit: "回/分",
      description: "",
    },
    {
      label: "警告閾値",
      value: config?.warningThresholdPct ?? 80,
      unit: "%",
      description: "",
    },
  ];

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        コスト管理設定はサーバー環境変数で管理されています。変更にはサーバー再起動が必要です。
      </p>
      {items.map((item) => (
        <div key={item.label}>
          <label className="text-sm font-medium">{item.label}</label>
          <div className="flex items-center gap-2">
            <Input
              type="number"
              value={item.value}
              disabled
              className="bg-muted"
              readOnly
            />
            <span className="text-xs text-muted-foreground whitespace-nowrap">
              {item.unit}
            </span>
          </div>
          {item.description && (
            <p className="mt-0.5 text-xs text-muted-foreground">
              {item.description}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

/* ================================================================
 * Account Settings
 * GET /api/v1/account
 * PUT /api/v1/account
 * ================================================================ */
function AccountSettings() {
  const { data: account, mutate } = useSWR<AccountInfo>(
    "/api/v1/account",
    fetcher
  );
  const [form, setForm] = useState({ email: "", displayName: "" });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (account) {
      setForm({
        email: account.email || "",
        displayName: account.displayName || "",
      });
    }
  }, [account]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const body: Record<string, string> = {};
      if (form.email && form.email !== account?.email) body.email = form.email;
      if (form.displayName !== (account?.displayName || ""))
        body.displayName = form.displayName;
      if (Object.keys(body).length === 0) {
        setSaving(false);
        return;
      }
      await apiClient.put("/api/v1/account", body);
      await mutate();
    } catch {
      // Error handled by apiClient
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="text-sm font-medium">表示名</label>
        <Input
          value={form.displayName}
          onChange={(e) =>
            setForm((f) => ({ ...f, displayName: e.target.value }))
          }
          placeholder="表示名を入力"
        />
      </div>
      <div>
        <label className="text-sm font-medium">メールアドレス</label>
        <Input
          type="email"
          value={form.email}
          onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
          placeholder="メールアドレスを入力"
        />
      </div>
      <Button onClick={handleSave} disabled={saving}>
        {saving ? "更新中..." : "更新"}
      </Button>
    </div>
  );
}

/* ================================================================
 * Main SettingsPage
 * ================================================================ */
const sectionComponents: Record<SettingsSection, () => JSX.Element> = {
  exchange: ExchangeSettings,
  ai: AISettings,
  safeguard: SafeguardSettings,
  cost: CostSettings,
  account: AccountSettings,
};

export function SettingsPage() {
  const [active, setActive] = useState<SettingsSection>("exchange");
  const SectionComponent = sectionComponents[active];

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <div className="flex flex-1">
        {/* Left menu */}
        <aside className="w-56 border-r p-4">
          <h3 className="mb-2 text-sm font-medium text-muted-foreground">
            システム設定
          </h3>
          <div className="space-y-1">
            {sections.map((s) => (
              <button
                key={s.key}
                onClick={() => setActive(s.key)}
                className={cn(
                  "w-full rounded-md px-3 py-2 text-left text-sm transition-colors",
                  active === s.key
                    ? "bg-accent text-accent-foreground"
                    : "hover:bg-accent/50"
                )}
              >
                {s.label}
              </button>
            ))}
          </div>

          {/* Sub links */}
          <div className="mt-6 border-t pt-4">
            <h3 className="mb-2 text-sm font-medium text-muted-foreground">
              ログ・履歴
            </h3>
            <div className="space-y-1">
              {subLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="block w-full rounded-md px-3 py-2 text-left text-sm text-muted-foreground hover:bg-accent/50 hover:text-accent-foreground"
                >
                  {link.label}
                </Link>
              ))}
            </div>
          </div>
        </aside>

        {/* Right content */}
        <main className="flex-1 p-6">
          <Card className={active === "safeguard" ? "max-w-2xl" : "max-w-lg"}>
            <CardHeader>
              <CardTitle className="text-base">
                {sections.find((s) => s.key === active)?.label}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <SectionComponent />
            </CardContent>
          </Card>
        </main>
      </div>
    </div>
  );
}
