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

interface M3M4TabProps {
  m3: StageConfig;
  m4: StageConfig;
  onM3Change: (field: string, value: unknown) => void;
  onM4Change: (field: string, value: unknown) => void;
}

const modeOptions = [
  { value: "rule", label: "ルール" },
  { value: "aiAssist", label: "AIアシスト" },
  { value: "aiFull", label: "AIフル" },
];

export function M3M4Tab({ m3, m4, onM3Change, onM4Change }: M3M4TabProps) {
  return (
    <div className="space-y-6">
      {/* M3 Entry */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">M3: エントリー実行</CardTitle>
            <Switch
              checked={m3.enabled}
              onCheckedChange={(v) => onM3Change("enabled", v)}
            />
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium">エントリー方式</label>
              <Select
                value={(m3.params.entryType as string) || "market"}
                options={[
                  { value: "market", label: "成行" },
                  { value: "limit", label: "指値" },
                ]}
                onChange={(e) => onM3Change("params.entryType", e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs font-medium">モード</label>
              <Select
                value={m3.mode}
                options={modeOptions}
                onChange={(e) => onM3Change("mode", e.target.value)}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium">TP/SL 方式</label>
              <Select
                value={(m3.params.tpSlMode as string) || "fixedPips"}
                options={[
                  { value: "fixedPips", label: "固定pips" },
                  { value: "atr", label: "ATRベース" },
                ]}
                onChange={(e) => onM3Change("params.tpSlMode", e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs font-medium">リスク%</label>
              <Input
                type="number"
                min={0.1}
                max={5}
                step={0.1}
                value={(m3.params.riskPct as number) || 1.0}
                onChange={(e) =>
                  onM3Change("params.riskPct", Number(e.target.value))
                }
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* M4 Exit */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">M4: 退出管理</CardTitle>
            <Switch
              checked={m4.enabled}
              onCheckedChange={(v) => onM4Change("enabled", v)}
            />
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <label className="text-xs font-medium">管理モード</label>
            <Select
              value={(m4.params.managementMode as string) || "passive"}
              options={[
                { value: "passive", label: "パッシブ（TP/SLのみ）" },
                { value: "active", label: "アクティブ（トレーリング、BE、部分決済）" },
              ]}
              onChange={(e) =>
                onM4Change("params.managementMode", e.target.value)
              }
            />
          </div>
          <div className="flex flex-wrap gap-4">
            <label className="flex items-center gap-2 text-sm">
              <Switch
                checked={(m4.params.breakEven as boolean) ?? false}
                onCheckedChange={(v) => onM4Change("params.breakEven", v)}
              />
              ブレイクイーブン
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Switch
                checked={(m4.params.trailingStop as boolean) ?? false}
                onCheckedChange={(v) => onM4Change("params.trailingStop", v)}
              />
              トレーリングストップ
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Switch
                checked={(m4.params.partialClose as boolean) ?? false}
                onCheckedChange={(v) => onM4Change("params.partialClose", v)}
              />
              部分決済
            </label>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium">最大保有時間（分）</label>
              <Input
                type="number"
                min={0}
                value={(m4.params.maxHoldTimeMin as number) || 0}
                onChange={(e) =>
                  onM4Change("params.maxHoldTimeMin", Number(e.target.value))
                }
              />
              <p className="mt-0.5 text-xs text-muted-foreground">0 = 無制限</p>
            </div>
            <div>
              <label className="text-xs font-medium">モード</label>
              <Select
                value={m4.mode}
                options={modeOptions}
                onChange={(e) => onM4Change("mode", e.target.value)}
              />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
