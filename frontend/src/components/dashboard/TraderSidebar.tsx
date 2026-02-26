"use client";

import { useState } from "react";
import { LayoutGrid, List } from "lucide-react";
import { cn } from "@/lib/utils";
import { TraderCard } from "./TraderCard";
import type { TraderSummary } from "@/types/api";

interface TraderSidebarProps {
  traders: TraderSummary[];
}

export function TraderSidebar({ traders }: TraderSidebarProps) {
  const [viewMode, setViewMode] = useState<"tile" | "list">("tile");

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-bold">AIトレーダー</h2>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setViewMode("tile")}
            className={cn(
              "rounded-md p-1",
              viewMode === "tile"
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:bg-accent"
            )}
          >
            <LayoutGrid className="h-4 w-4" />
          </button>
          <button
            onClick={() => setViewMode("list")}
            className={cn(
              "rounded-md p-1",
              viewMode === "list"
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:bg-accent"
            )}
          >
            <List className="h-4 w-4" />
          </button>
        </div>
      </div>

      {traders.length === 0 ? (
        <p className="py-4 text-center text-sm text-muted-foreground">
          トレーダーが登録されていません
        </p>
      ) : (
        <div className="space-y-3">
          {traders.map((trader) => (
            <TraderCard key={trader.traderId} trader={trader} />
          ))}
        </div>
      )}
    </div>
  );
}
