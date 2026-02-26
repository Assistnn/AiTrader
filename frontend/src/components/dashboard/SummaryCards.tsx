"use client";

import { Wallet, TrendingUp, Users } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { formatJpy } from "@/lib/utils";
import type { DashboardSummary } from "@/types/api";

interface SummaryCardsProps {
  summary: DashboardSummary;
}

export function SummaryCards({ summary }: SummaryCardsProps) {
  const items = [
    {
      label: "本日損益",
      value: formatJpy(summary.totalPnlToday),
      icon: TrendingUp,
      colorClass: summary.totalPnlToday >= 0 ? "text-profit" : "text-loss",
    },
    {
      label: "月間損益",
      value: formatJpy(summary.totalPnlMonth),
      icon: Wallet,
      colorClass: summary.totalPnlMonth >= 0 ? "text-profit" : "text-loss",
    },
    {
      label: "稼働中トレーダー",
      value: `${summary.activeTraders} / ${summary.traders.length}`,
      icon: Users,
      colorClass: "text-foreground",
    },
  ];

  return (
    <div className="grid grid-cols-3 gap-4">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <Card key={item.label}>
            <CardContent className="flex items-center gap-3 p-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted">
                <Icon className="h-5 w-5 text-muted-foreground" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">{item.label}</p>
                <p className={`text-lg font-bold ${item.colorClass}`}>
                  {item.value}
                </p>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
