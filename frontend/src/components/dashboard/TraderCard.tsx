"use client";

import { useRouter } from "next/navigation";
import { Play, Square, Settings, History, TrendingUp, TrendingDown, Minus, ShieldAlert, ShieldCheck } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatJpy } from "@/lib/utils";
import { apiClient } from "@/lib/api";
import type { TraderSummary } from "@/types/api";

interface TraderCardProps {
  trader: TraderSummary;
}

const statusConfig: Record<string, { label: string; variant: "success" | "secondary" | "destructive" }> = {
  running: { label: "稼働中", variant: "success" },
  stopped: { label: "停止中", variant: "secondary" },
  error: { label: "エラー", variant: "destructive" },
  halted: { label: "停止", variant: "destructive" },
};

export function TraderCard({ trader }: TraderCardProps) {
  const router = useRouter();
  const status = statusConfig[trader.status] || statusConfig.stopped;
  const isRunning = trader.status === "running";

  const handleToggle = async () => {
    const action = isRunning ? "stop" : "start";
    try {
      await apiClient.post(`/api/v1/traders/${trader.traderId}/${action}`);
    } catch {
      // Error handled by apiClient
    }
  };

  return (
    <Card>
      <CardContent className="p-3 space-y-2">
        {/* Header: name + status */}
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">{trader.traderName}</span>
          <Badge variant={status.variant}>{status.label}</Badge>
        </div>

        {/* PnL and open positions */}
        <div className="flex items-center justify-between text-sm">
          <div>
            <span className="text-xs text-muted-foreground">本日損益: </span>
            <span className={trader.pnlToday >= 0 ? "text-profit" : "text-loss"}>
              {formatJpy(trader.pnlToday)}
            </span>
          </div>
          <div>
            <span className="text-xs text-muted-foreground">ポジション: </span>
            <span>{trader.openPositions}</span>
          </div>
        </div>

        {/* Pipeline state indicators */}
        {trader.pipelineState && (
          <div className="flex items-center gap-2 text-xs">
            {trader.pipelineState.lastM1 && (
              <span className="flex items-center gap-0.5 text-muted-foreground" title="M1 方向判定">
                M1:
                {(trader.pipelineState.lastM1 as Record<string, unknown>).direction === "UP" ? (
                  <TrendingUp className="h-3 w-3 text-profit" />
                ) : (trader.pipelineState.lastM1 as Record<string, unknown>).direction === "DOWN" ? (
                  <TrendingDown className="h-3 w-3 text-loss" />
                ) : (
                  <Minus className="h-3 w-3" />
                )}
              </span>
            )}
            {trader.pipelineState.guardState && (
              <span className="flex items-center gap-0.5 text-muted-foreground" title="ガード状態">
                {(trader.pipelineState.guardState as { status?: string }).status === "normal" ? (
                  <ShieldCheck className="h-3 w-3 text-profit" />
                ) : (
                  <ShieldAlert className="h-3 w-3 text-yellow-500" />
                )}
              </span>
            )}
          </div>
        )}

        {/* Action buttons */}
        <div className="flex items-center gap-1 pt-1">
          <button
            onClick={handleToggle}
            className={`rounded-md px-2 py-1 text-xs ${
              isRunning
                ? "text-destructive hover:bg-destructive/10"
                : "text-profit hover:bg-profit/10"
            }`}
            title={isRunning ? "停止" : "開始"}
          >
            {isRunning ? (
              <Square className="h-3.5 w-3.5" />
            ) : (
              <Play className="h-3.5 w-3.5" />
            )}
          </button>
          <button
            onClick={() => router.push("/history")}
            className="rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-accent"
            title="履歴を見る"
          >
            <History className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => router.push("/traders")}
            className="ml-auto rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-accent"
            title="設定"
          >
            <Settings className="h-3.5 w-3.5" />
          </button>
        </div>
      </CardContent>
    </Card>
  );
}
