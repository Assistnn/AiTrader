"use client";

/**
 * セーフガード設定パネル（SG-001〜SG-040 / 6カテゴリ）
 * Reference: 06_セーフガード, 08_API仕様 Section 3-6
 *
 * API:
 *   GET /api/v1/traders/{traderId}/safeguards
 *   PUT /api/v1/traders/{traderId}/safeguards
 */

import { useState, useEffect } from "react";
import useSWR from "swr";
import { ChevronDown, ChevronRight, Shield } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { apiClient, fetcher } from "@/lib/api";

interface SafeguardConfig {
  id: number;
  traderId: number;
  configJson: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

/** Default config matching guard_rules.py defaults */
function defaultConfig(): Record<string, unknown> {
  return {
    maxDailyLossPct: 2.0,
    maxMonthlyLossPct: 5.0,
    maxDrawdownPct: 10.0,
    stopOnProfit: { enabled: false, targetPct: 3.0 },
    consecutiveLoss: { enabled: true, maxCount: 3, cooldownMinutes: 60, halveLot: false },
    spread: { showAverage: true, showCurrent: true, anomalyMultiplier: 3.0 },
    atrSpike: { enabled: true, lookback: 14, maxMultiplier: 2.5 },
    rangeSpike: { enabled: true, windowMinutes: 5, maxPips: 50 },
    session: {
      blockOutsideTokyo: false,
      blockOutsideLondon: false,
      blockOutsideNY: false,
      startBuffer: { enabled: true, minutes: 30 },
      endBuffer: { enabled: true, minutes: 30 },
      lowVolStop: false,
    },
    econStop: { enabled: true, importance: "high", beforeMinutes: 30, afterMinutes: 15, scope: "tradedOnly" },
    regime: { trendBreakdown: false, adxDrop: false, rangeTransition: false },
    exec: { maxPositions: 5, sameDirectionLimit: 3, correlatedBlock: false },
    aiFailsafe: { timeout: true, invalidOutput: true, lowConfidence: true },
  };
}

/* ================================================================
 * Generic field renderer
 * ================================================================ */
function NumberField({
  label,
  value,
  onChange,
  unit,
  description,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  unit?: string;
  description?: string;
}) {
  return (
    <div className="flex items-start gap-3 py-2">
      <div className="flex-1">
        <label className="text-sm font-medium">{label}</label>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
      </div>
      <div className="flex items-center gap-1">
        <Input
          type="number"
          className="w-24 text-right"
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
        />
        {unit && (
          <span className="text-xs text-muted-foreground whitespace-nowrap">
            {unit}
          </span>
        )}
      </div>
    </div>
  );
}

function SwitchField({
  label,
  checked,
  onChange,
  description,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  description?: string;
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <div>
        <label className="text-sm font-medium">{label}</label>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
      </div>
      <Switch checked={checked} onCheckedChange={onChange} />
    </div>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <label className="text-sm font-medium">{label}</label>
      <Select
        value={value}
        options={options}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

/* ================================================================
 * Category section
 * ================================================================ */
function Category({
  title,
  codes,
  defaultOpen,
  children,
}: {
  title: string;
  codes: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen ?? false);

  return (
    <div className="border rounded-lg">
      <button
        className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-accent/30"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-2">
          <Shield className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-semibold">{title}</span>
          <span className="text-xs text-muted-foreground">({codes})</span>
        </div>
        {open ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}
      </button>
      {open && <div className="border-t px-4 pb-3 divide-y">{children}</div>}
    </div>
  );
}

/* ================================================================
 * Main Panel
 * ================================================================ */
export function SafeguardSettingsPanel({
  traderId,
}: {
  traderId: number;
}) {
  const { data: config, mutate } = useSWR<SafeguardConfig>(
    traderId ? `/api/v1/traders/${traderId}/safeguards` : null,
    fetcher
  );
  const [form, setForm] = useState<Record<string, unknown>>(defaultConfig());
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (config?.configJson) {
      setForm((prev) => ({ ...defaultConfig(), ...config.configJson }));
    }
  }, [config]);

  // Helpers for nested access
  const get = <T,>(path: string, fallback: T): T => {
    const parts = path.split(".");
    let val: unknown = form;
    for (const p of parts) {
      if (val == null || typeof val !== "object") return fallback;
      val = (val as Record<string, unknown>)[p];
    }
    return (val ?? fallback) as T;
  };

  const set = (path: string, value: unknown) => {
    setForm((prev) => {
      const parts = path.split(".");
      if (parts.length === 1) return { ...prev, [parts[0]]: value };
      const root = { ...prev };
      const parent = parts.slice(0, -1).reduce<Record<string, unknown>>((obj, key) => {
        const child = obj[key];
        const copy = typeof child === "object" && child !== null ? { ...(child as Record<string, unknown>) } : {};
        obj[key] = copy;
        return copy;
      }, root);
      parent[parts[parts.length - 1]] = value;
      return root;
    });
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.put(`/api/v1/traders/${traderId}/safeguards`, form);
      await mutate();
    } catch {
      // Error handled by apiClient
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3">
      {/* Category 1: 資金保護 SG-001〜SG-009 */}
      <Category title="資金保護" codes="SG-001〜SG-009" defaultOpen>
        <NumberField
          label="SG-001: 日次最大損失率"
          value={get("maxDailyLossPct", 2.0)}
          onChange={(v) => set("maxDailyLossPct", v)}
          unit="%"
        />
        <NumberField
          label="SG-002: 月次最大損失率"
          value={get("maxMonthlyLossPct", 5.0)}
          onChange={(v) => set("maxMonthlyLossPct", v)}
          unit="%"
        />
        <NumberField
          label="SG-003: 最大ドローダウン"
          value={get("maxDrawdownPct", 10.0)}
          onChange={(v) => set("maxDrawdownPct", v)}
          unit="%"
        />
        <SwitchField
          label="SG-004: 利益達成時停止"
          checked={get("stopOnProfit.enabled", false)}
          onChange={(v) => set("stopOnProfit.enabled", v)}
        />
        <NumberField
          label="SG-005: 利益目標"
          value={get("stopOnProfit.targetPct", 3.0)}
          onChange={(v) => set("stopOnProfit.targetPct", v)}
          unit="%"
        />
        <SwitchField
          label="SG-006: 連続損失制御"
          checked={get("consecutiveLoss.enabled", true)}
          onChange={(v) => set("consecutiveLoss.enabled", v)}
        />
        <NumberField
          label="SG-007: 最大連続損失数"
          value={get("consecutiveLoss.maxCount", 3)}
          onChange={(v) => set("consecutiveLoss.maxCount", v)}
          unit="回"
        />
        <NumberField
          label="SG-008: クールダウン時間"
          value={get("consecutiveLoss.cooldownMinutes", 60)}
          onChange={(v) => set("consecutiveLoss.cooldownMinutes", v)}
          unit="分"
        />
        <SwitchField
          label="SG-009: ロット半減"
          checked={get("consecutiveLoss.halveLot", false)}
          onChange={(v) => set("consecutiveLoss.halveLot", v)}
        />
      </Category>

      {/* Category 2: 市場異常検知 SG-010〜SG-018 */}
      <Category title="市場異常検知" codes="SG-010〜SG-018">
        <SwitchField
          label="SG-010: スプレッド平均表示"
          checked={get("spread.showAverage", true)}
          onChange={(v) => set("spread.showAverage", v)}
        />
        <SwitchField
          label="SG-011: スプレッド現在値表示"
          checked={get("spread.showCurrent", true)}
          onChange={(v) => set("spread.showCurrent", v)}
        />
        <NumberField
          label="SG-012: スプレッド異常倍率"
          value={get("spread.anomalyMultiplier", 3.0)}
          onChange={(v) => set("spread.anomalyMultiplier", v)}
          unit="倍"
        />
        <SwitchField
          label="SG-013: ATR急増検知"
          checked={get("atrSpike.enabled", true)}
          onChange={(v) => set("atrSpike.enabled", v)}
        />
        <NumberField
          label="SG-014: ATRルックバック本数"
          value={get("atrSpike.lookback", 14)}
          onChange={(v) => set("atrSpike.lookback", v)}
          unit="本"
        />
        <NumberField
          label="SG-015: ATR最大倍率"
          value={get("atrSpike.maxMultiplier", 2.5)}
          onChange={(v) => set("atrSpike.maxMultiplier", v)}
          unit="倍"
        />
        <SwitchField
          label="SG-016: 急変動検知"
          checked={get("rangeSpike.enabled", true)}
          onChange={(v) => set("rangeSpike.enabled", v)}
        />
        <NumberField
          label="SG-017: 急変動ウィンドウ"
          value={get("rangeSpike.windowMinutes", 5)}
          onChange={(v) => set("rangeSpike.windowMinutes", v)}
          unit="分"
        />
        <NumberField
          label="SG-018: 急変動最大Pips"
          value={get("rangeSpike.maxPips", 50)}
          onChange={(v) => set("rangeSpike.maxPips", v)}
          unit="pips"
        />
      </Category>

      {/* Category 3: 取引時間制御 SG-019〜SG-026 */}
      <Category title="取引時間制御" codes="SG-019〜SG-026">
        <SwitchField
          label="SG-019: 東京時間外禁止"
          checked={get("session.blockOutsideTokyo", false)}
          onChange={(v) => set("session.blockOutsideTokyo", v)}
        />
        <SwitchField
          label="SG-020: ロンドン時間外禁止"
          checked={get("session.blockOutsideLondon", false)}
          onChange={(v) => set("session.blockOutsideLondon", v)}
        />
        <SwitchField
          label="SG-021: NY時間外禁止"
          checked={get("session.blockOutsideNY", false)}
          onChange={(v) => set("session.blockOutsideNY", v)}
        />
        <SwitchField
          label="SG-022: セッション開始バッファ"
          checked={get("session.startBuffer.enabled", true)}
          onChange={(v) => set("session.startBuffer.enabled", v)}
        />
        <NumberField
          label="SG-023: 開始バッファ時間"
          value={get("session.startBuffer.minutes", 30)}
          onChange={(v) => set("session.startBuffer.minutes", v)}
          unit="分"
        />
        <SwitchField
          label="SG-024: セッション終了バッファ"
          checked={get("session.endBuffer.enabled", true)}
          onChange={(v) => set("session.endBuffer.enabled", v)}
        />
        <NumberField
          label="SG-025: 終了バッファ時間"
          value={get("session.endBuffer.minutes", 30)}
          onChange={(v) => set("session.endBuffer.minutes", v)}
          unit="分"
        />
        <SwitchField
          label="SG-026: 低ボラティリティ停止"
          checked={get("session.lowVolStop", false)}
          onChange={(v) => set("session.lowVolStop", v)}
        />
      </Category>

      {/* Category 4: 経済指標フィルター SG-027〜SG-031 */}
      <Category title="経済指標フィルター" codes="SG-027〜SG-031">
        <SwitchField
          label="SG-027: 重要指標前停止"
          checked={get("econStop.enabled", true)}
          onChange={(v) => set("econStop.enabled", v)}
        />
        <SelectField
          label="SG-028: 重要度フィルタ"
          value={get("econStop.importance", "high")}
          options={[
            { value: "low", label: "低" },
            { value: "medium", label: "中" },
            { value: "high", label: "高" },
          ]}
          onChange={(v) => set("econStop.importance", v)}
        />
        <NumberField
          label="SG-029: 発表前停止時間"
          value={get("econStop.beforeMinutes", 30)}
          onChange={(v) => set("econStop.beforeMinutes", v)}
          unit="分"
        />
        <NumberField
          label="SG-030: 発表後停止時間"
          value={get("econStop.afterMinutes", 15)}
          onChange={(v) => set("econStop.afterMinutes", v)}
          unit="分"
        />
        <SelectField
          label="SG-031: 対象通貨スコープ"
          value={get("econStop.scope", "tradedOnly")}
          options={[
            { value: "all", label: "全通貨" },
            { value: "tradedOnly", label: "取引通貨のみ" },
          ]}
          onChange={(v) => set("econStop.scope", v)}
        />
      </Category>

      {/* Category 5: レジーム保護 SG-032〜SG-034 */}
      <Category title="レジーム保護" codes="SG-032〜SG-034">
        <SwitchField
          label="SG-032: トレンド崩壊時停止"
          checked={get("regime.trendBreakdown", false)}
          onChange={(v) => set("regime.trendBreakdown", v)}
        />
        <SwitchField
          label="SG-033: ADX低下時停止"
          checked={get("regime.adxDrop", false)}
          onChange={(v) => set("regime.adxDrop", v)}
        />
        <SwitchField
          label="SG-034: レンジ移行時停止"
          checked={get("regime.rangeTransition", false)}
          onChange={(v) => set("regime.rangeTransition", v)}
        />
      </Category>

      {/* Category 6: 実行保護 SG-035〜SG-040 */}
      <Category title="実行保護" codes="SG-035〜SG-040">
        <NumberField
          label="SG-035: 最大同時ポジション数"
          value={get("exec.maxPositions", 5)}
          onChange={(v) => set("exec.maxPositions", v)}
          unit="件"
        />
        <NumberField
          label="SG-036: 同方向ポジション制限"
          value={get("exec.sameDirectionLimit", 3)}
          onChange={(v) => set("exec.sameDirectionLimit", v)}
          unit="件"
        />
        <SwitchField
          label="SG-037: 相関通貨同時禁止"
          checked={get("exec.correlatedBlock", false)}
          onChange={(v) => set("exec.correlatedBlock", v)}
        />
        <SwitchField
          label="SG-038: AI応答遅延時停止"
          checked={get("aiFailsafe.timeout", true)}
          onChange={(v) => set("aiFailsafe.timeout", v)}
        />
        <SwitchField
          label="SG-039: AI出力異常時停止"
          checked={get("aiFailsafe.invalidOutput", true)}
          onChange={(v) => set("aiFailsafe.invalidOutput", v)}
        />
        <SwitchField
          label="SG-040: confidence未達時フォールバック"
          checked={get("aiFailsafe.lowConfidence", true)}
          onChange={(v) => set("aiFailsafe.lowConfidence", v)}
        />
      </Category>

      {/* Save button */}
      <div className="pt-2">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "保存中..." : "セーフガード設定を保存"}
        </Button>
      </div>
    </div>
  );
}
