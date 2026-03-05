"use client";

import { useState } from "react";
import { Header } from "@/components/common/Header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useTradeHistory } from "@/hooks/useDashboard";
import { apiClient, API_BASE } from "@/lib/api";
import { formatJpy, formatPips, formatDateJst } from "@/lib/utils";
import type { TradeRecord } from "@/types/api";
import type { StageResult } from "@/types/api";

function StageDetail({ label, stage }: { label: string; stage: StageResult }) {
  return (
    <div className="rounded border p-2 text-xs">
      <div className="mb-1 flex items-center justify-between">
        <span className="font-medium">{label}</span>
        <span className="text-muted-foreground">{stage.elapsedMs}ms</span>
      </div>
      <div className="flex flex-wrap gap-1">
        {stage.reasonCodes.map((code) => (
          <Badge key={code} variant="outline" className="text-[10px]">
            {code}
          </Badge>
        ))}
      </div>
      <p className="mt-1 text-muted-foreground">
        信頼度: {(stage.confidence * 100).toFixed(0)}%
      </p>
    </div>
  );
}

function TradeRow({ trade }: { trade: TradeRecord }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border-b last:border-b-0">
      <button
        className="flex w-full items-center gap-3 px-4 py-3 text-sm hover:bg-accent/50"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="w-28 text-left text-xs text-muted-foreground">
          {trade.closedAt ? formatDateJst(trade.closedAt) : "-"}
        </span>
        <span className="w-20">{trade.pair}</span>
        <Badge variant={trade.side === "BUY" ? "success" : "destructive"}>
          {trade.side === "BUY" ? "買い" : "売り"}
        </Badge>
        <span className="w-24 text-right tabular-nums">
          {trade.entryPrice?.toFixed(3) ?? "-"}
        </span>
        <span className="w-24 text-right tabular-nums">
          {trade.exitPrice?.toFixed(3) ?? "-"}
        </span>
        <span
          className={`w-24 text-right tabular-nums ${
            (trade.realizedPnl ?? 0) >= 0 ? "text-profit" : "text-loss"
          }`}
        >
          {trade.realizedPnl != null ? formatJpy(trade.realizedPnl) : "-"}
        </span>
        <span className="w-20 text-right tabular-nums text-muted-foreground">
          {trade.realizedPnlPips != null ? formatPips(trade.realizedPnlPips) : "-"}
        </span>
        <span className="ml-auto text-muted-foreground">
          {expanded ? "\u25B2" : "\u25BC"}
        </span>
      </button>

      {expanded && trade.pipelineLogs && (
        <div className="bg-muted/30 px-4 py-3">
          <p className="mb-2 text-xs font-medium text-muted-foreground">
            パイプライン詳細 (ID: {trade.pipelineLogs.executionId})
          </p>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <StageDetail label="M1: 方向判定" stage={trade.pipelineLogs.m1} />
            <StageDetail label="M2: セットアップ" stage={trade.pipelineLogs.m2} />
            <StageDetail label="M3: エントリー" stage={trade.pipelineLogs.m3} />
            {trade.pipelineLogs.m4 && (
              <StageDetail label="M4: 退出" stage={trade.pipelineLogs.m4} />
            )}
          </div>
          {trade.pipelineLogs.guardState.blockingGuards.length > 0 && (
            <div className="mt-2">
              <span className="text-xs font-medium text-yellow-500">
                ブロック中のガード:{" "}
              </span>
              {trade.pipelineLogs.guardState.blockingGuards.map((g) => (
                <Badge key={g} variant="warning" className="mr-1 text-[10px]">
                  {g}
                </Badge>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function TradeHistoryPage() {
  const [page, setPage] = useState(1);
  const { data: result, isLoading, error } = useTradeHistory(page);

  const items = result?.data ?? [];
  const totalPages = result?.pagination?.totalPages ?? 1;
  const totalItems = result?.pagination?.totalItems ?? 0;

  const handleCsvExport = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/history/export/csv`, {
        headers: { Authorization: `Bearer ${(apiClient as any).token || ""}` },
      });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "trade_history.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // Error handling
    }
  };

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1 p-4">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>取引履歴</CardTitle>
              <div className="flex items-center gap-2">
                {totalItems > 0 && (
                  <span className="text-sm text-muted-foreground">
                    {totalItems}件
                  </span>
                )}
                <Button variant="outline" size="sm" onClick={handleCsvExport}>
                  CSVエクスポート
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {/* Header */}
            <div className="flex items-center gap-3 border-b px-4 py-2 text-xs font-medium text-muted-foreground">
              <span className="w-28">日付</span>
              <span className="w-20">通貨ペア</span>
              <span className="w-14">売買</span>
              <span className="w-24 text-right">エントリー</span>
              <span className="w-24 text-right">決済</span>
              <span className="w-24 text-right">損益</span>
              <span className="w-20 text-right">Pips</span>
            </div>

            {isLoading && (
              <p className="py-8 text-center text-muted-foreground">読み込み中...</p>
            )}
            {error && (
              <p className="py-8 text-center text-destructive">{error.message}</p>
            )}
            {items.length === 0 && !isLoading && (
              <p className="py-8 text-center text-muted-foreground">
                取引履歴がありません
              </p>
            )}
            {items.map((trade) => (
              <TradeRow key={trade.id} trade={trade} />
            ))}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 pt-4">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                >
                  前へ
                </Button>
                <span className="text-sm text-muted-foreground">
                  {page} / {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage(page + 1)}
                >
                  次へ
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
