"use client";

import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type { Trader } from "@/types/api";

interface BasicInfoTabProps {
  trader: Trader;
  onChange: (field: string, value: unknown) => void;
}

const tradeTypeOptions = [
  { value: "fx", label: "FX" },
  { value: "crypto", label: "Crypto" },
];

const fxPairs = [
  { value: "USD_JPY", label: "USD/JPY" },
  { value: "EUR_JPY", label: "EUR/JPY" },
  { value: "GBP_JPY", label: "GBP/JPY" },
  { value: "EUR_USD", label: "EUR/USD" },
];

const cryptoPairs = [
  { value: "BTC_JPY", label: "BTC/JPY" },
  { value: "ETH_JPY", label: "ETH/JPY" },
  { value: "XRP_JPY", label: "XRP/JPY" },
];

export function BasicInfoTab({ trader, onChange }: BasicInfoTabProps) {
  const pairOptions = trader.tradeType === "fx" ? fxPairs : cryptoPairs;

  return (
    <div className="space-y-4">
      <div>
        <label className="text-sm font-medium">Trader Name</label>
        <Input
          value={trader.name}
          onChange={(e) => onChange("name", e.target.value)}
        />
      </div>
      <div>
        <label className="text-sm font-medium">Trade Type</label>
        <Select
          value={trader.tradeType}
          options={tradeTypeOptions}
          onChange={(e) => onChange("tradeType", e.target.value)}
        />
      </div>
      <div>
        <label className="text-sm font-medium">Pair</label>
        <Select
          value={trader.pair}
          options={pairOptions}
          onChange={(e) => onChange("pair", e.target.value)}
        />
      </div>
      <div>
        <label className="text-sm font-medium">Capital (JPY)</label>
        <Input
          type="number"
          value={trader.capital}
          onChange={(e) => onChange("capital", Number(e.target.value))}
        />
      </div>
      <div>
        <label className="text-sm font-medium">Lot Size</label>
        <Input
          type="number"
          value={trader.lotSize}
          step="0.01"
          onChange={(e) => onChange("lotSize", Number(e.target.value))}
        />
      </div>
      <div>
        <label className="text-sm font-medium">Strategy Text</label>
        <textarea
          className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          value={trader.strategyText}
          onChange={(e) => onChange("strategyText", e.target.value)}
          maxLength={2000}
        />
        <p className="mt-1 text-xs text-muted-foreground">
          {trader.strategyText.length} / 2000
        </p>
      </div>
    </div>
  );
}
