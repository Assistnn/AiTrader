"use client";

import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type { Trader } from "@/types/api";
import { getPairOptions } from "@/constants/pairs";

interface BasicInfoTabProps {
  trader: Trader;
  onChange: (field: string, value: unknown) => void;
}

const tradeTypeOptions = [
  { value: "FX", label: "FX" },
  { value: "Crypto", label: "仮想通貨" },
];

export function BasicInfoTab({ trader, onChange }: BasicInfoTabProps) {
  const pairOptions = getPairOptions(trader.tradeType);
  const primaryPair = trader.symbols?.[0] || "";

  return (
    <div className="space-y-4">
      <div>
        <label className="text-sm font-medium">トレーダー名</label>
        <Input
          value={trader.traderName}
          onChange={(e) => onChange("traderName", e.target.value)}
        />
      </div>
      <div>
        <label className="text-sm font-medium">取引タイプ</label>
        <Select
          value={trader.tradeType}
          options={tradeTypeOptions}
          onChange={(e) => onChange("tradeType", e.target.value)}
        />
      </div>
      <div>
        <label className="text-sm font-medium">通貨ペア</label>
        <Select
          value={primaryPair}
          options={pairOptions}
          onChange={(e) => onChange("symbols", [e.target.value])}
        />
      </div>
      <div>
        <label className="text-sm font-medium">資金 (JPY)</label>
        <Input
          type="number"
          value={trader.capitalJpy}
          onChange={(e) => onChange("capitalJpy", Number(e.target.value))}
        />
      </div>
      <div>
        <label className="text-sm font-medium">ロットサイズ</label>
        <Input
          type="number"
          value={trader.orderUnitLots}
          step="0.01"
          onChange={(e) => onChange("orderUnitLots", Number(e.target.value))}
        />
      </div>
      <div>
        <label className="text-sm font-medium">戦略テキスト</label>
        <textarea
          className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          value={trader.strategyText || ""}
          onChange={(e) => onChange("strategyText", e.target.value)}
          maxLength={2000}
        />
        <p className="mt-1 text-xs text-muted-foreground">
          {(trader.strategyText || "").length} / 2000
        </p>
      </div>
    </div>
  );
}
