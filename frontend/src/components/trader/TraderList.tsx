"use client";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import type { Trader } from "@/types/api";

interface TraderListProps {
  traders: Trader[];
  activeId: number | null;
  onSelect: (trader: Trader) => void;
}

const statusLabels: Record<string, string> = {
  running: "稼働中",
  stopped: "停止中",
  error: "エラー",
};

export function TraderList({ traders, activeId, onSelect }: TraderListProps) {
  return (
    <div className="space-y-1">
      <h3 className="mb-2 text-sm font-medium text-muted-foreground">
        トレーダー一覧
      </h3>
      {traders.map((t) => (
        <button
          key={t.id}
          onClick={() => onSelect(t)}
          className={cn(
            "flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors",
            activeId === t.id
              ? "border border-blue-500 bg-blue-50 text-foreground dark:bg-blue-950/50"
              : "hover:bg-accent/50"
          )}
        >
          <div className="text-left">
            <span className="font-medium">{t.traderName}</span>
            <p className="text-xs text-muted-foreground">
              {t.symbols?.[0]?.replace("_", "/") || t.tradeType}
            </p>
          </div>
          <Badge
            variant={
              t.status === "running"
                ? "success"
                : t.status === "error"
                ? "destructive"
                : "secondary"
            }
          >
            {statusLabels[t.status] || t.status}
          </Badge>
        </button>
      ))}
    </div>
  );
}
