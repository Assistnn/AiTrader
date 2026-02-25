"use client";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import type { Trader } from "@/types/api";

interface TraderListProps {
  traders: Trader[];
  activeId: number | null;
  onSelect: (trader: Trader) => void;
}

export function TraderList({ traders, activeId, onSelect }: TraderListProps) {
  return (
    <div className="space-y-1">
      <h3 className="mb-2 text-sm font-medium text-muted-foreground">
        Traders
      </h3>
      {traders.map((t) => (
        <button
          key={t.id}
          onClick={() => onSelect(t)}
          className={cn(
            "flex w-full items-center justify-between rounded-md px-3 py-2 text-sm transition-colors",
            activeId === t.id
              ? "bg-accent text-accent-foreground"
              : "hover:bg-accent/50"
          )}
        >
          <span>{t.name}</span>
          <Badge
            variant={
              t.status === "running"
                ? "success"
                : t.status === "error"
                ? "destructive"
                : "secondary"
            }
          >
            {t.status}
          </Badge>
        </button>
      ))}
    </div>
  );
}
