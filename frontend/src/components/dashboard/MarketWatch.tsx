"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useDashboardStore } from "@/stores/dashboardStore";
import type { PriceQuote } from "@/types/api";

function PriceRow({ price }: { price: PriceQuote }) {
  const spread = price.ask - price.bid;
  return (
    <div className="flex items-center justify-between py-1.5 text-sm">
      <span className="font-medium">{price.pair}</span>
      <div className="flex gap-4 tabular-nums">
        <span className="text-green-500">{price.bid.toFixed(3)}</span>
        <span className="text-red-500">{price.ask.toFixed(3)}</span>
        <span className="w-16 text-right text-muted-foreground">
          {spread.toFixed(1)}
        </span>
      </div>
    </div>
  );
}

export function MarketWatch() {
  const prices = useDashboardStore((s) => s.prices);
  const priceList = Object.values(prices);

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Market Watch</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between pb-1 text-xs text-muted-foreground">
          <span>Pair</span>
          <div className="flex gap-4">
            <span>Bid</span>
            <span>Ask</span>
            <span className="w-16 text-right">Spread</span>
          </div>
        </div>
        <div className="divide-y">
          {priceList.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">
              Waiting for price data...
            </p>
          ) : (
            priceList.map((p) => <PriceRow key={p.pair} price={p} />)
          )}
        </div>
      </CardContent>
    </Card>
  );
}
