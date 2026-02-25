"use client";

import { useState } from "react";
import { Header } from "@/components/common/Header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useTradeHistory } from "@/hooks/useDashboard";
import { formatJpy, formatPips, formatDateJst } from "@/lib/utils";
import type { TradeRecord, StageResult } from "@/types/api";

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
        Confidence: {(stage.confidence * 100).toFixed(0)}%
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
          {formatDateJst(trade.exitTimestamp)}
        </span>
        <span className="w-20">{trade.pair}</span>
        <Badge variant={trade.side === "BUY" ? "success" : "destructive"}>
          {trade.side}
        </Badge>
        <span className="w-24 text-right tabular-nums">
          {trade.entryPrice.toFixed(3)}
        </span>
        <span className="w-24 text-right tabular-nums">
          {trade.exitPrice.toFixed(3)}
        </span>
        <span
          className={`w-24 text-right tabular-nums ${
            trade.realizedPnl >= 0 ? "text-green-500" : "text-red-500"
          }`}
        >
          {formatJpy(trade.realizedPnl)}
        </span>
        <span className="w-20 text-right tabular-nums text-muted-foreground">
          {formatPips(trade.realizedPnlPips)}
        </span>
        <span className="ml-auto text-muted-foreground">
          {expanded ? "\u25B2" : "\u25BC"}
        </span>
      </button>

      {expanded && trade.pipelineLogs && (
        <div className="bg-muted/30 px-4 py-3">
          <p className="mb-2 text-xs font-medium text-muted-foreground">
            Pipeline Details (ID: {trade.pipelineLogs.executionId})
          </p>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <StageDetail label="M1: Direction" stage={trade.pipelineLogs.m1} />
            <StageDetail label="M2: Setup" stage={trade.pipelineLogs.m2} />
            <StageDetail label="M3: Entry" stage={trade.pipelineLogs.m3} />
            {trade.pipelineLogs.m4 && (
              <StageDetail label="M4: Exit" stage={trade.pipelineLogs.m4} />
            )}
          </div>
          {trade.pipelineLogs.guardState.blockingGuards.length > 0 && (
            <div className="mt-2">
              <span className="text-xs font-medium text-yellow-500">
                Blocking Guards:{" "}
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
  const { data, isLoading, error } = useTradeHistory(page);

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1 p-4">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Trade History</CardTitle>
              <Button variant="outline" size="sm">
                Export CSV
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {/* Header */}
            <div className="flex items-center gap-3 border-b px-4 py-2 text-xs font-medium text-muted-foreground">
              <span className="w-28">Date</span>
              <span className="w-20">Pair</span>
              <span className="w-14">Side</span>
              <span className="w-24 text-right">Entry</span>
              <span className="w-24 text-right">Exit</span>
              <span className="w-24 text-right">P&L</span>
              <span className="w-20 text-right">Pips</span>
            </div>

            {isLoading && (
              <p className="py-8 text-center text-muted-foreground">Loading...</p>
            )}
            {error && (
              <p className="py-8 text-center text-red-500">{error.message}</p>
            )}
            {data && data.items.length === 0 && (
              <p className="py-8 text-center text-muted-foreground">
                No trades yet
              </p>
            )}
            {data?.items.map((trade) => (
              <TradeRow key={trade.id} trade={trade} />
            ))}

            {/* Pagination */}
            {data && data.totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 pt-4">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                >
                  Prev
                </Button>
                <span className="text-sm text-muted-foreground">
                  {page} / {data.totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= data.totalPages}
                  onClick={() => setPage(page + 1)}
                >
                  Next
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
