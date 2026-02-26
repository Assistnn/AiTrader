"use client";

import { Header } from "@/components/common/Header";
import { SummaryCards } from "@/components/dashboard/SummaryCards";
import { MarketWatch } from "@/components/dashboard/MarketWatch";
import { TraderSidebar } from "@/components/dashboard/TraderSidebar";
import { ActionButtons } from "@/components/dashboard/ActionButtons";
import { ChartPanel } from "@/components/dashboard/ChartPanel";
import { useDashboardSummary } from "@/hooks/useDashboard";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useAuthStore } from "@/stores/authStore";

export function DashboardPage() {
  const { data: summary, error, isLoading } = useDashboardSummary();
  const accessToken = useAuthStore((s) => s.accessToken);

  // Connect WebSocket for real-time price updates
  useWebSocket(accessToken);

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1 overflow-hidden">
        {isLoading && (
          <p className="p-8 text-center text-muted-foreground">読み込み中...</p>
        )}
        {error && (
          <p className="p-8 text-center text-destructive">
            ダッシュボードの読み込みに失敗しました: {error.message}
          </p>
        )}
        {summary && (
          <div className="grid h-[calc(100vh-3.5rem)] grid-cols-[280px_1fr_320px]">
            {/* Left: MarketWatch */}
            <aside className="overflow-y-auto border-r p-4">
              <MarketWatch />
            </aside>

            {/* Center: Summary + Actions + Chart */}
            <div className="flex flex-col gap-4 overflow-y-auto p-4">
              <SummaryCards summary={summary} />
              <ActionButtons />
              <ChartPanel />
            </div>

            {/* Right: Trader Sidebar */}
            <aside className="overflow-y-auto border-l p-4">
              <TraderSidebar traders={summary.traders} />
            </aside>
          </div>
        )}
      </main>
    </div>
  );
}
