"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatJpy } from "@/lib/utils";
import type { Trader } from "@/types/api";

interface TraderCardProps {
  trader: Trader;
}

function TrendIcon({ trend }: { trend: "UP" | "DOWN" | "NEUTRAL" }) {
  if (trend === "UP") return <span className="text-green-500">&#9650;</span>;
  if (trend === "DOWN") return <span className="text-red-500">&#9660;</span>;
  return <span className="text-muted-foreground">&#9644;</span>;
}

function GuardIndicator({ status }: { status: "normal" | "warning" | "halted" }) {
  const config = {
    normal: { color: "bg-green-500", label: "Normal" },
    warning: { color: "bg-yellow-500", label: "Warning" },
    halted: { color: "bg-red-500", label: "Halted" },
  };
  const { color, label } = config[status];
  return (
    <span className="inline-flex items-center gap-1.5 text-xs">
      <span className={`h-2 w-2 rounded-full ${color}`} />
      {label}
    </span>
  );
}

export function TraderCard({ trader }: TraderCardProps) {
  const statusVariant =
    trader.status === "running"
      ? "success"
      : trader.status === "error"
      ? "destructive"
      : "secondary";

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">{trader.name}</CardTitle>
          <Badge variant={statusVariant}>{trader.status}</Badge>
        </div>
        <p className="text-xs text-muted-foreground">
          {trader.pair} / {trader.tradeType.toUpperCase()}
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Pipeline State */}
        <div className="flex items-center gap-4 text-sm">
          <div className="flex items-center gap-1">
            <span className="text-xs text-muted-foreground">M1:</span>
            {trader.pipelineState ? (
              <TrendIcon trend={trader.pipelineState.m1Trend} />
            ) : (
              <span className="text-xs text-muted-foreground">--</span>
            )}
          </div>
          <div className="flex items-center gap-1">
            <span className="text-xs text-muted-foreground">M2:</span>
            <span className="text-xs">
              {trader.pipelineState?.m2Setup || "--"}
            </span>
          </div>
          <div className="ml-auto">
            <GuardIndicator
              status={trader.guardState?.status || "normal"}
            />
          </div>
        </div>

        {/* P&L */}
        <div className="flex items-center justify-between text-sm">
          <div>
            <span className="text-xs text-muted-foreground">Daily: </span>
            <span
              className={
                trader.dailyPnl >= 0 ? "text-green-500" : "text-red-500"
              }
            >
              {formatJpy(trader.dailyPnl)}
            </span>
          </div>
          <div>
            <span className="text-xs text-muted-foreground">Monthly: </span>
            <span
              className={
                trader.monthlyPnl >= 0 ? "text-green-500" : "text-red-500"
              }
            >
              {formatJpy(trader.monthlyPnl)}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
