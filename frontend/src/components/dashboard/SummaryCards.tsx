"use client";

import { Card, CardContent } from "@/components/ui/card";
import { formatJpy } from "@/lib/utils";
import type { DashboardSummary } from "@/types/api";

interface SummaryCardsProps {
  summary: DashboardSummary;
}

export function SummaryCards({ summary }: SummaryCardsProps) {
  const items = [
    {
      label: "Daily P&L",
      value: formatJpy(summary.totalDailyPnl),
      color: summary.totalDailyPnl >= 0 ? "text-green-500" : "text-red-500",
    },
    {
      label: "Monthly P&L",
      value: formatJpy(summary.totalMonthlyPnl),
      color: summary.totalMonthlyPnl >= 0 ? "text-green-500" : "text-red-500",
    },
    {
      label: "Active Traders",
      value: String(summary.traders.filter((t) => t.status === "running").length),
      color: "text-foreground",
    },
    {
      label: "Open Positions",
      value: String(summary.activePositions),
      color: "text-foreground",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      {items.map((item) => (
        <Card key={item.label}>
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground">{item.label}</p>
            <p className={`text-xl font-bold ${item.color}`}>{item.value}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
