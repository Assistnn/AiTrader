"use client";

import { useState, useEffect } from "react";
import useSWR from "swr";
import { Header } from "@/components/common/Header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Bell, Mail, Clock, Trash2, Plus, Send } from "lucide-react";
import { cn } from "@/lib/utils";
import { apiClient, fetcher } from "@/lib/api";
import type {
  SmtpConfig,
  NotificationEmailItem,
  DailyNotificationConfig,
} from "@/types/api";

type Section = "smtp" | "emails" | "daily" | "triggers";

const sections: { key: Section; label: string; icon: typeof Bell }[] = [
  { key: "smtp", label: "SMTP設定", icon: Mail },
  { key: "emails", label: "通知メールアドレス", icon: Mail },
  { key: "daily", label: "デイリー通知", icon: Clock },
  { key: "triggers", label: "通知トリガー", icon: Bell },
];

/* ================================================================
 * SMTP設定
 * GET /api/v1/notifications/smtp
 * PUT /api/v1/notifications/smtp
 * POST /api/v1/notifications/test
 * ================================================================ */
function SmtpSettings() {
  const { data: config, mutate } = useSWR<SmtpConfig>(
    "/api/v1/notifications/smtp",
    fetcher
  );
  const [form, setForm] = useState({
    host: "",
    port: 587,
    username: "",
    password: "",
    fromAddress: "",
    useTls: true,
  });
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    if (config) {
      setForm((prev) => ({
        ...prev,
        host: config.host || "",
        port: config.port || 587,
        username: config.username || "",
        fromAddress: config.fromAddress || "",
        useTls: config.useTls,
      }));
    }
  }, [config]);

  const handleChange = (field: string, value: unknown) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.put("/api/v1/notifications/smtp", {
        host: form.host,
        port: form.port,
        username: form.username,
        ...(form.password ? { password: form.password } : {}),
        useTls: form.useTls,
        fromAddress: form.fromAddress,
      });
      setForm((prev) => ({ ...prev, password: "" }));
      await mutate();
    } catch {
      // Error handled by apiClient
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      await apiClient.post("/api/v1/notifications/test");
    } catch {
      // Error handled by apiClient
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="text-sm font-medium">SMTPホスト</label>
          <Input
            placeholder="smtp.example.com"
            value={form.host}
            onChange={(e) => handleChange("host", e.target.value)}
          />
        </div>
        <div>
          <label className="text-sm font-medium">ポート</label>
          <Input
            type="number"
            value={form.port}
            onChange={(e) => handleChange("port", Number(e.target.value))}
          />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="text-sm font-medium">ユーザー名</label>
          <Input
            value={form.username}
            onChange={(e) => handleChange("username", e.target.value)}
          />
        </div>
        <div>
          <label className="text-sm font-medium">パスワード</label>
          <Input
            type="password"
            placeholder="••••••••"
            value={form.password}
            onChange={(e) => handleChange("password", e.target.value)}
          />
        </div>
      </div>
      <div>
        <label className="text-sm font-medium">送信元アドレス</label>
        <Input
          type="email"
          placeholder="noreply@example.com"
          value={form.fromAddress}
          onChange={(e) => handleChange("fromAddress", e.target.value)}
        />
      </div>
      <label className="flex items-center gap-2 text-sm">
        <Switch
          checked={form.useTls}
          onCheckedChange={(v) => handleChange("useTls", v)}
        />
        TLS/SSLを使用する
      </label>
      <div className="flex items-center gap-3 pt-2">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "保存中..." : "保存"}
        </Button>
        <Button variant="outline" disabled={testing} onClick={handleTest}>
          <Send className="mr-1.5 h-4 w-4" />
          {testing ? "送信中..." : "テスト送信"}
        </Button>
      </div>
    </div>
  );
}

/* ================================================================
 * 通知メールアドレス管理
 * GET /api/v1/notifications/emails
 * POST /api/v1/notifications/emails
 * DELETE /api/v1/notifications/emails/{id}
 * ================================================================ */
function EmailManagement() {
  const { data: emails, mutate } = useSWR<NotificationEmailItem[]>(
    "/api/v1/notifications/emails",
    fetcher
  );
  const [newEmail, setNewEmail] = useState("");
  const [adding, setAdding] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const handleAdd = async () => {
    if (!newEmail.includes("@")) return;
    setAdding(true);
    try {
      await apiClient.post("/api/v1/notifications/emails", {
        email: newEmail,
        isActive: true,
      });
      setNewEmail("");
      await mutate();
    } catch {
      // Error handled by apiClient
    } finally {
      setAdding(false);
    }
  };

  const handleRemove = async (id: number) => {
    setDeletingId(id);
    try {
      await apiClient.del(`/api/v1/notifications/emails/${id}`);
      await mutate();
    } catch {
      // Error handled by apiClient
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        通知の送信先メールアドレスを管理します。複数のアドレスを登録できます。
      </p>

      {/* Add new email */}
      <div className="flex items-center gap-2">
        <Input
          type="email"
          placeholder="user@example.com"
          value={newEmail}
          onChange={(e) => setNewEmail(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAdd()}
        />
        <Button
          onClick={handleAdd}
          disabled={!newEmail.includes("@") || adding}
        >
          <Plus className="mr-1.5 h-4 w-4" />
          {adding ? "追加中..." : "追加"}
        </Button>
      </div>

      {/* Email list */}
      {(!emails || emails.length === 0) ? (
        <p className="py-4 text-center text-sm text-muted-foreground">
          通知先メールアドレスが登録されていません
        </p>
      ) : (
        <div className="divide-y rounded-lg border">
          {emails.map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between px-4 py-3"
            >
              <div className="flex items-center gap-3">
                <span
                  className={cn(
                    "text-sm",
                    !item.isActive && "text-muted-foreground line-through"
                  )}
                >
                  {item.email}
                </span>
                {item.isActive && (
                  <Badge variant="success">有効</Badge>
                )}
              </div>
              <button
                onClick={() => handleRemove(item.id)}
                disabled={deletingId === item.id}
                className="rounded-md p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive disabled:opacity-50"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ================================================================
 * デイリー通知設定
 * GET /api/v1/notifications/daily
 * PUT /api/v1/notifications/daily
 * ================================================================ */
function DailyNotificationSettings() {
  const { data: config, mutate } = useSWR<DailyNotificationConfig>(
    "/api/v1/notifications/daily",
    fetcher
  );
  const [form, setForm] = useState({
    enabled: false,
    sendTimeUtc: "22:00",
    includePnl: true,
    includeTrades: true,
    includeGuards: true,
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (config) {
      setForm({
        enabled: config.enabled,
        sendTimeUtc: config.sendTimeUtc || "22:00",
        includePnl: config.includePnl,
        includeTrades: config.includeTrades,
        includeGuards: config.includeGuards,
      });
    }
  }, [config]);

  const handleChange = (field: string, value: unknown) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.put("/api/v1/notifications/daily", {
        enabled: form.enabled,
        sendTimeUtc: form.sendTimeUtc,
        includePnl: form.includePnl,
        includeTrades: form.includeTrades,
        includeGuards: form.includeGuards,
      });
      await mutate();
    } catch {
      // Error handled by apiClient
    } finally {
      setSaving(false);
    }
  };

  // UTC→JST変換の簡易表示
  const utcHour = parseInt(form.sendTimeUtc.split(":")[0], 10);
  const jstHour = (utcHour + 9) % 24;
  const jstDisplay = `${String(jstHour).padStart(2, "0")}:${form.sendTimeUtc.split(":")[1]}`;

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        毎日のトレーディングサマリーをメールで受信できます。
      </p>

      <label className="flex items-center gap-2 text-sm font-medium">
        <Switch
          checked={form.enabled}
          onCheckedChange={(v) => handleChange("enabled", v)}
        />
        デイリー通知を有効にする
      </label>

      {form.enabled && (
        <div className="space-y-4 rounded-lg border bg-card p-4">
          <div>
            <label className="text-sm font-medium">送信時刻 (UTC)</label>
            <Input
              type="time"
              value={form.sendTimeUtc}
              onChange={(e) => handleChange("sendTimeUtc", e.target.value)}
            />
            <p className="mt-1 text-xs text-muted-foreground">
              日本時間: {jstDisplay} JST
            </p>
          </div>

          <div className="space-y-3">
            <p className="text-sm font-medium">通知に含める内容</p>
            <label className="flex items-center gap-2 text-sm">
              <Switch
                checked={form.includePnl}
                onCheckedChange={(v) => handleChange("includePnl", v)}
              />
              損益情報
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Switch
                checked={form.includeTrades}
                onCheckedChange={(v) => handleChange("includeTrades", v)}
              />
              取引情報
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Switch
                checked={form.includeGuards}
                onCheckedChange={(v) => handleChange("includeGuards", v)}
              />
              セーフガード発動情報
            </label>
          </div>

          <Button onClick={handleSave} disabled={saving}>
            {saving ? "保存中..." : "保存"}
          </Button>
        </div>
      )}
    </div>
  );
}

/* ================================================================
 * 通知トリガー設定 (ローカルstate管理 — バックエンドAPIなし)
 * ================================================================ */
function TriggerSettings() {
  const triggers = [
    { key: "notifyOnEntry", label: "エントリー時", description: "新規ポジションが建てられた時" },
    { key: "notifyOnExit", label: "決済時", description: "ポジションが決済された時" },
    { key: "notifyOnTarget", label: "利確時", description: "利確ターゲットに到達した時" },
    { key: "notifyOnStop", label: "ストップ時", description: "ストップロスが発動した時" },
    { key: "notifyOnError", label: "エラー時", description: "トレーダーにエラーが発生した時" },
    { key: "safeguardTriggered", label: "セーフガード発動時", description: "セーフガードルールが発動した時" },
    { key: "pipelineAlert", label: "パイプラインアラート", description: "パイプライン実行で異常が検知された時" },
  ];

  const [enabled, setEnabled] = useState<Record<string, boolean>>(
    Object.fromEntries(triggers.map((t) => [t.key, true]))
  );

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        リアルタイム通知のトリガーを設定します。個別トレーダーの通知設定はトレーダー設定画面から行えます。
      </p>

      <div className="divide-y rounded-lg border">
        {triggers.map((trigger) => (
          <div
            key={trigger.key}
            className="flex items-center justify-between px-4 py-3"
          >
            <div>
              <p className="text-sm font-medium">{trigger.label}</p>
              <p className="text-xs text-muted-foreground">
                {trigger.description}
              </p>
            </div>
            <Switch
              checked={enabled[trigger.key]}
              onCheckedChange={(v) =>
                setEnabled((prev) => ({ ...prev, [trigger.key]: v }))
              }
            />
          </div>
        ))}
      </div>

      <p className="text-xs text-muted-foreground">
        通知トリガーの設定はサーバー側での対応予定です。
      </p>
    </div>
  );
}

/* ================================================================
 * メインページ
 * ================================================================ */
const sectionComponents: Record<Section, () => JSX.Element> = {
  smtp: SmtpSettings,
  emails: EmailManagement,
  daily: DailyNotificationSettings,
  triggers: TriggerSettings,
};

export function NotificationSettingsPage() {
  const [active, setActive] = useState<Section>("smtp");
  const SectionComponent = sectionComponents[active];

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <div className="flex flex-1">
        {/* Left menu */}
        <aside className="w-56 border-r p-4">
          <h3 className="mb-2 text-sm font-medium text-muted-foreground">
            通知設定
          </h3>
          <div className="space-y-1">
            {sections.map((s) => {
              const Icon = s.icon;
              return (
                <button
                  key={s.key}
                  onClick={() => setActive(s.key)}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors",
                    active === s.key
                      ? "bg-accent text-accent-foreground"
                      : "hover:bg-accent/50"
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {s.label}
                </button>
              );
            })}
          </div>
        </aside>

        {/* Right content */}
        <main className="flex-1 p-6">
          <Card className="max-w-2xl">
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
