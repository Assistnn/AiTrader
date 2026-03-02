"use client";

import { useState } from "react";
import useSWR from "swr";
import { Plus, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useDashboardStore } from "@/stores/dashboardStore";
import { apiClient, fetcher } from "@/lib/api";
import type { PriceQuote } from "@/types/api";
import { FX_PAIRS, CRYPTO_PAIRS, formatPairLabel, isCryptoPair } from "@/constants/pairs";

interface MarketWatchItem {
  id: number;
  pair: string;
  displayOrder: number;
  isVisible: boolean;
}

const AVAILABLE_PAIRS = [
  ...FX_PAIRS.map((p) => ({ value: p, label: formatPairLabel(p), group: "FX" })),
  ...CRYPTO_PAIRS.map((p) => ({ value: p, label: formatPairLabel(p), group: "仮想通貨" })),
];

function PriceRow({
  price,
  onRemove,
  removing,
}: {
  price: PriceQuote;
  onRemove: () => void;
  removing: boolean;
}) {
  const spread = price.ask - price.bid;
  const decimals = isCryptoPair(price.pair) ? 1 : 3;

  return (
    <div className="group flex items-center justify-between py-2 text-sm">
      <div className="flex items-center gap-2">
        <span className="font-medium">{price.pair}</span>
      </div>
      <div className="flex items-center gap-3 tabular-nums">
        <span className="text-bid">{price.bid.toFixed(decimals)}</span>
        <span className="text-ask">{price.ask.toFixed(decimals)}</span>
        <span className="w-14 text-right text-xs text-muted-foreground">
          {spread.toFixed(1)}
        </span>
        <button
          onClick={onRemove}
          disabled={removing}
          className="invisible rounded p-0.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive group-hover:visible disabled:opacity-50"
        >
          <X className="h-3 w-3" />
        </button>
      </div>
    </div>
  );
}

export function MarketWatch() {
  const prices = useDashboardStore((s) => s.prices);
  const { data: watchList, mutate } = useSWR<MarketWatchItem[]>(
    "/api/v1/market-watch",
    fetcher
  );
  const [showAdd, setShowAdd] = useState(false);
  const [adding, setAdding] = useState(false);
  const [removingId, setRemovingId] = useState<number | null>(null);

  // Determine which pairs to display
  const watchedPairs = watchList?.map((w) => w.pair) ?? [];
  const allPrices = Object.values(prices);

  // If watch list loaded, show only watched pairs; otherwise show all
  const displayPrices =
    watchList !== undefined && watchedPairs.length > 0
      ? watchedPairs
          .map((pair) => allPrices.find((p) => p.pair === pair))
          .filter((p): p is PriceQuote => p !== undefined)
      : allPrices;

  const fxPairs = displayPrices.filter((p) => !isCryptoPair(p.pair));
  const cryptoPairs = displayPrices.filter((p) => isCryptoPair(p.pair));

  const addablePairs = AVAILABLE_PAIRS.filter(
    (ap) => !watchedPairs.includes(ap.value)
  );

  const handleAdd = async (pair: string) => {
    setAdding(true);
    try {
      await apiClient.post("/api/v1/market-watch", {
        pair,
        displayOrder: watchedPairs.length,
      });
      await mutate();
    } catch {
      // Error handled by apiClient
    } finally {
      setAdding(false);
      setShowAdd(false);
    }
  };

  const handleRemove = async (id: number) => {
    setRemovingId(id);
    try {
      await apiClient.del(`/api/v1/market-watch/${id}`);
      await mutate();
    } catch {
      // Error handled by apiClient
    } finally {
      setRemovingId(null);
    }
  };

  const findWatchId = (pair: string) =>
    watchList?.find((w) => w.pair === pair)?.id;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-bold">マーケットウォッチ</h2>
        <div className="relative">
          <button
            onClick={() => setShowAdd(!showAdd)}
            className="flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground hover:bg-accent"
          >
            <Plus className="h-4 w-4" />
          </button>

          {/* Add pair dropdown */}
          {showAdd && (
            <div className="absolute right-0 top-8 z-10 w-48 rounded-lg border bg-popover p-2 shadow-md">
              <p className="mb-1 text-xs font-medium text-muted-foreground">
                ペアを追加
              </p>
              {addablePairs.length === 0 ? (
                <p className="py-2 text-center text-xs text-muted-foreground">
                  追加可能なペアがありません
                </p>
              ) : (
                addablePairs.map((ap) => (
                  <button
                    key={ap.value}
                    onClick={() => handleAdd(ap.value)}
                    disabled={adding}
                    className="flex w-full items-center justify-between rounded px-2 py-1.5 text-sm hover:bg-accent disabled:opacity-50"
                  >
                    <span>{ap.label}</span>
                    <span className="text-xs text-muted-foreground">
                      {ap.group}
                    </span>
                  </button>
                ))
              )}
            </div>
          )}
        </div>
      </div>

      {/* Header */}
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>通貨ペア</span>
        <div className="flex gap-3">
          <span className="text-bid">Bid</span>
          <span className="text-ask">Ask</span>
          <span className="w-14 text-right">スプレッド</span>
          <span className="invisible w-5" />
        </div>
      </div>

      {displayPrices.length === 0 ? (
        <p className="py-4 text-center text-sm text-muted-foreground">
          価格データを待機中...
        </p>
      ) : (
        <>
          {/* FX Section */}
          {fxPairs.length > 0 && (
            <div>
              <p className="mb-1 text-xs font-medium text-muted-foreground">
                FX
              </p>
              <div className="divide-y">
                {fxPairs.map((p) => {
                  const wId = findWatchId(p.pair);
                  return (
                    <PriceRow
                      key={p.pair}
                      price={p}
                      onRemove={() => wId && handleRemove(wId)}
                      removing={removingId === wId}
                    />
                  );
                })}
              </div>
            </div>
          )}

          {/* Crypto Section */}
          {cryptoPairs.length > 0 && (
            <div>
              <p className="mb-1 text-xs font-medium text-muted-foreground">
                仮想通貨
              </p>
              <div className="divide-y">
                {cryptoPairs.map((p) => {
                  const wId = findWatchId(p.pair);
                  return (
                    <PriceRow
                      key={p.pair}
                      price={p}
                      onRemove={() => wId && handleRemove(wId)}
                      removing={removingId === wId}
                    />
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
