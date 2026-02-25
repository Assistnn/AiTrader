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
  { value: "rule", label: "Rule" },
  { value: "aiAssist", label: "AI Assist" },
  { value: "aiFull", label: "AI Full" },
];

const timeframeOptions = [
  { value: "M5", label: "M5" },
  { value: "M15", label: "M15" },
  { value: "M30", label: "M30" },
  { value: "H1", label: "H1" },
  { value: "H4", label: "H4" },
  { value: "D1", label: "D1" },
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
            <CardTitle className="text-base">M1: Direction & Regime</CardTitle>
            <Switch
              checked={m1.enabled}
              onCheckedChange={(v) => onM1Change("enabled", v)}
            />
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium">Timeframe</label>
              <Select
                value={m1.timeframe}
                options={timeframeOptions}
                onChange={(e) => onM1Change("timeframe", e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs font-medium">Mode</label>
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
                <label className="text-xs font-medium">AI Provider</label>
                <Select
                  value={(m1.params.aiProvider as string) || "openai"}
                  options={providerOptions}
                  onChange={(e) => onM1Change("params.aiProvider", e.target.value)}
                />
              </div>
              <div>
                <label className="text-xs font-medium">Min Confidence</label>
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
              Trend
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Switch
                checked={(m1.params.rangeAvoidance as boolean) ?? true}
                onCheckedChange={(v) => onM1Change("params.rangeAvoidance", v)}
              />
              Range Avoidance
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Switch
                checked={(m1.params.volatilityEnabled as boolean) ?? true}
                onCheckedChange={(v) => onM1Change("params.volatilityEnabled", v)}
              />
              Volatility
            </label>
          </div>
        </CardContent>
      </Card>

      {/* M2 Setup Detection */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">M2: Setup Detection</CardTitle>
            <Switch
              checked={m2.enabled}
              onCheckedChange={(v) => onM2Change("enabled", v)}
            />
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium">Timeframe</label>
              <Select
                value={m2.timeframe}
                options={timeframeOptions}
                onChange={(e) => onM2Change("timeframe", e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs font-medium">Mode</label>
              <Select
                value={m2.mode}
                options={modeOptions}
                onChange={(e) => onM2Change("mode", e.target.value)}
              />
            </div>
          </div>
          <div>
            <label className="text-xs font-medium">Setup Preset</label>
            <Select
              value={(m2.params.setupPreset as string) || "trendFollowing"}
              options={[
                { value: "trendFollowing", label: "Trend Following" },
                { value: "meanReversion", label: "Mean Reversion" },
                { value: "breakout", label: "Breakout" },
                { value: "custom", label: "Custom" },
              ]}
              onChange={(e) => onM2Change("params.setupPreset", e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs font-medium">Probability Threshold</label>
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
