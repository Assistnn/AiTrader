"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";

interface StageConfig {
  enabled: boolean;
  mode: string;
  timeframe: string;
  params: Record<string, unknown>;
}

interface M1M2TabProps {
  m1: StageConfig;
  m2: StageConfig;
  onM1Change: (field: string, value: unknown) => void;
  onM2Change: (field: string, value: unknown) => void;
}

const modeOptions = [
  { value: "rule", label: "ルール" },
  { value: "aiAssist", label: "AIアシスト" },
  { value: "aiFull", label: "AIフル" },
];

const timeframeOptions = [
  { value: "M5", label: "5分" },
  { value: "M15", label: "15分" },
  { value: "M30", label: "30分" },
  { value: "H1", label: "1時間" },
  { value: "H4", label: "4時間" },
  { value: "D1", label: "日足" },
];

const providerOptions = [
  { value: "openai", label: "OpenAI" },
  { value: "gemini", label: "Gemini" },
  { value: "claude", label: "Claude" },
];

export function M1M2Tab({ m1, m2, onM1Change, onM2Change }: M1M2TabProps) {
  return (
    <div className="space-y-6">
      {/* M1 Direction & Regime */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">M1: 方向判定</CardTitle>
            <Switch
              checked={m1.enabled}
              onCheckedChange={(v) => onM1Change("enabled", v)}
            />
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium">時間足</label>
              <Select
                value={m1.timeframe}
                options={timeframeOptions}
                onChange={(e) => onM1Change("timeframe", e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs font-medium">モード</label>
              <Select
                value={m1.mode}
                options={modeOptions}
                onChange={(e) => onM1Change("mode", e.target.value)}
              />
            </div>
          </div>
          {m1.mode !== "rule" && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium">AIプロバイダー</label>
                <Select
                  value={(m1.params.aiProvider as string) || "openai"}
                  options={providerOptions}
                  onChange={(e) => onM1Change("params.aiProvider", e.target.value)}
                />
              </div>
              <div>
                <label className="text-xs font-medium">最小信頼度</label>
                <Input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={(m1.params.minConfidence as number) || 0.7}
                  onChange={(e) =>
                    onM1Change("params.minConfidence", Number(e.target.value))
                  }
                />
              </div>
            </div>
          )}
          <div className="flex flex-wrap gap-4">
            <label className="flex items-center gap-2 text-sm">
              <Switch
                checked={(m1.params.trendEnabled as boolean) ?? true}
                onCheckedChange={(v) => onM1Change("params.trendEnabled", v)}
              />
              トレンド
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Switch
                checked={(m1.params.rangeAvoidance as boolean) ?? true}
                onCheckedChange={(v) => onM1Change("params.rangeAvoidance", v)}
              />
              レンジ回避
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Switch
                checked={(m1.params.volatilityEnabled as boolean) ?? true}
                onCheckedChange={(v) => onM1Change("params.volatilityEnabled", v)}
              />
              ボラティリティ
            </label>
          </div>
        </CardContent>
      </Card>

      {/* M2 Setup Detection */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">M2: セットアップ検出</CardTitle>
            <Switch
              checked={m2.enabled}
              onCheckedChange={(v) => onM2Change("enabled", v)}
            />
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium">時間足</label>
              <Select
                value={m2.timeframe}
                options={timeframeOptions}
                onChange={(e) => onM2Change("timeframe", e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs font-medium">モード</label>
              <Select
                value={m2.mode}
                options={modeOptions}
                onChange={(e) => onM2Change("mode", e.target.value)}
              />
            </div>
          </div>
          <div>
            <label className="text-xs font-medium">セットアッププリセット</label>
            <Select
              value={(m2.params.setupPreset as string) || "trendFollowing"}
              options={[
                { value: "trendFollowing", label: "トレンドフォロー" },
                { value: "meanReversion", label: "平均回帰" },
                { value: "breakout", label: "ブレイクアウト" },
                { value: "custom", label: "カスタム" },
              ]}
              onChange={(e) => onM2Change("params.setupPreset", e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs font-medium">確率閾値</label>
            <Input
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={(m2.params.probabilityThreshold as number) || 0.6}
              onChange={(e) =>
                onM2Change("params.probabilityThreshold", Number(e.target.value))
              }
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
