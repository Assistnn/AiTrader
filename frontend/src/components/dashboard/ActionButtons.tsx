"use client";

import { useState } from "react";
import { Square, Play, X } from "lucide-react";
import { apiClient } from "@/lib/api";
import { useDashboardStore } from "@/stores/dashboardStore";

export function ActionButtons() {
  const [loading, setLoading] = useState<string | null>(null);

  const handleAction = async (action: "stop-all" | "start-all" | "close-all") => {
    setLoading(action);
    try {
      await apiClient.post(`/api/v1/dashboard/${action}`);
    } catch {
      // Error handled by apiClient (401 redirect etc.)
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={() => handleAction("close-all")}
        className="inline-flex items-center gap-1.5 rounded-lg border border-destructive px-4 py-2 text-sm font-medium text-destructive hover:bg-destructive/10 disabled:opacity-50"
        disabled={loading !== null}
      >
        <X className="h-4 w-4" />
        {loading === "close-all" ? "決済中..." : "全て決済"}
      </button>
      <button
        onClick={() => handleAction("stop-all")}
        disabled={loading !== null}
        className="inline-flex items-center gap-1.5 rounded-lg border px-4 py-2 text-sm font-medium text-foreground hover:bg-accent disabled:opacity-50"
      >
        <Square className="h-4 w-4" />
        {loading === "stop-all" ? "停止中..." : "全停止"}
      </button>
      <button
        onClick={() => handleAction("start-all")}
        disabled={loading !== null}
        className="inline-flex items-center gap-1.5 rounded-lg bg-foreground px-4 py-2 text-sm font-medium text-background hover:bg-foreground/90 disabled:opacity-50"
      >
        <Play className="h-4 w-4" />
        {loading === "start-all" ? "開始中..." : "全開始"}
      </button>
    </div>
  );
}
