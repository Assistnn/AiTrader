"use client";

import { Header } from "@/components/common/Header";
import { SummaryCards } from "@/components/dashboard/SummaryCards";
import { MarketWatch } from "@/components/dashboard/MarketWatch";
import { TraderSidebar } from "@/components/dashboard/TraderSidebar";
import { ActionButtons } from "@/components/dashboard/ActionButtons";
import { ChartPanel } from "@/components/dashboard/ChartPanel";
import { RecentTrades } from "@/components/dashboard/RecentTrades";
import { useDashboardSummary } from "@/hooks/useDashboard";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useAuthStore } from "@/stores/authStore";
import { Card, CardContent } from "@/components/ui/card";

function SkeletonBlock({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-muted ${className ?? ""}`} />;
}

function SummaryCardsSkeleton() {
  return (
    <div className="grid grid-cols-4 gap-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <Card key={i}>
          <CardContent className="p-4 space-y-2">
            <SkeletonBlock className="h-3 w-20" />
            <SkeletonBlock className="h-6 w-28" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function TraderSidebarSkeleton() {
  return (
    <div className="space-y-3">
      <SkeletonBlock className="h-5 w-32" />
      {Array.from({ length: 3 }).map((_, i) => (
        <Card key={i}>
          <CardContent className="p-3 space-y-2">
            <div className="flex items-center justify-between">
              <SkeletonBlock className="h-4 w-24" />
              <SkeletonBlock className="h-5 w-14 rounded-full" />
            </div>
            <SkeletonBlock className="h-3 w-32" />
            <SkeletonBlock className="h-3 w-20" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export function DashboardPage() {
  const { data: summary, error } = useDashboardSummary();
  const accessToken = useAuthStore((s) => s.accessToken);

  // Connect WebSocket for real-time price updates
  useWebSocket(accessToken);

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1 overflow-hidden">
        {error && (
          <p className="p-8 text-center text-destructive">
            ダッシュボードの読み込みに失敗しました: {error.message}
          </p>
        )}
        <div className="grid min-h-[calc(100vh-3.5rem)] grid-cols-[280px_1fr_320px]">
          {/* Left: MarketWatch (data-independent, always render) */}
          <aside className="overflow-y-auto border-r p-4">
            <MarketWatch />
          </aside>

          {/* Center: Summary + Actions + Chart + Recent Trades */}
          <div className="flex flex-col gap-4 p-4">
            {summary ? (
              <SummaryCards summary={summary} />
            ) : (
              <SummaryCardsSkeleton />
            )}
            <ActionButtons />
            <ChartPanel />
            <RecentTrades />
          </div>

          {/* Right: Trader Sidebar */}
          <aside className="overflow-y-auto border-l p-4">
            {summary ? (
              <TraderSidebar traders={summary.traders} />
            ) : (
              <TraderSidebarSkeleton />
            )}
          </aside>
        </div>
      </main>
    </div>
  );
}
