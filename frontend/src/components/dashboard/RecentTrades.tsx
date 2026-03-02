"use client";

import Link from "next/link";
import { History } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useTradeHistory } from "@/hooks/useDashboard";
import { formatJpy, formatDateJst } from "@/lib/utils";
import type { TradeRecord } from "@/types/api";

function TradeRowCompact({ trade }: { trade: TradeRecord }) {
  const pnl = trade.realizedPnl ?? 0;

  return (
    <tr className="border-b text-xs last:border-b-0 hover:bg-accent/30">
      <td className="px-3 py-2 text-muted-foreground whitespace-nowrap">
        {trade.closedAt ? formatDateJst(trade.closedAt) : trade.openedAt ? formatDateJst(trade.openedAt) : "-"}
      </td>
      <td className="px-3 py-2 whitespace-nowrap">{trade.pair.replace("_", "/")}</td>
      <td className="px-3 py-2">
        <Badge
          variant={trade.side === "BUY" ? "success" : "destructive"}
          className="text-[10px] px-1.5 py-0"
        >
          {trade.side === "BUY" ? "買" : "売"}
        </Badge>
      </td>
      <td className="px-3 py-2 text-right tabular-nums whitespace-nowrap">
        {trade.entryPrice?.toFixed(3) ?? "-"}
      </td>
      <td className="px-3 py-2 text-right tabular-nums whitespace-nowrap">
        {trade.exitPrice?.toFixed(3) ?? "-"}
      </td>
      <td
        className={`px-3 py-2 text-right tabular-nums whitespace-nowrap ${
          pnl >= 0 ? "text-profit" : "text-loss"
        }`}
      >
        {trade.realizedPnl != null ? formatJpy(trade.realizedPnl) : "-"}
      </td>
      <td className="px-3 py-2 text-center">
        {trade.closedAt ? (
          <Badge variant="outline" className="text-[10px] px-1.5 py-0">
            決済済
          </Badge>
        ) : (
          <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
            保有中
          </Badge>
        )}
      </td>
    </tr>
  );
}

export function RecentTrades() {
  const { data: result, isLoading, error } = useTradeHistory(1, 10);
  const items = result?.data ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <History className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">最近の取引履歴</span>
          {items.length > 0 && (
            <span className="text-xs text-muted-foreground">
              ({result?.pagination?.totalItems ?? 0}件中 最新{items.length}件)
            </span>
          )}
        </div>
        <Link
          href="/history"
          className="text-xs text-primary hover:underline"
        >
          全てを表示
        </Link>
      </div>

      <div className="rounded-lg border bg-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b bg-muted/30 text-xs text-muted-foreground">
                <th className="px-3 py-2 text-left font-medium">日時</th>
                <th className="px-3 py-2 text-left font-medium">通貨ペア</th>
                <th className="px-3 py-2 text-left font-medium">売買</th>
                <th className="px-3 py-2 text-right font-medium">エントリー</th>
                <th className="px-3 py-2 text-right font-medium">エグジット</th>
                <th className="px-3 py-2 text-right font-medium">損益</th>
                <th className="px-3 py-2 text-center font-medium">状態</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-sm text-muted-foreground">
                    読み込み中...
                  </td>
                </tr>
              )}
              {error && (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-sm text-destructive">
                    取引履歴の読み込みに失敗しました
                  </td>
                </tr>
              )}
              {!isLoading && !error && items.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-sm text-muted-foreground">
                    取引履歴がありません
                  </td>
                </tr>
              )}
              {items.map((trade) => (
                <TradeRowCompact key={trade.id} trade={trade} />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
