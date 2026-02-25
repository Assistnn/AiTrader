"use client";

import { Header } from "@/components/common/Header";
import { SummaryCards } from "@/components/dashboard/SummaryCards";
import { TraderCard } from "@/components/dashboard/TraderCard";
import { MarketWatch } from "@/components/dashboard/MarketWatch";
import { useDashboardSummary } from "@/hooks/useDashboard";

export function DashboardPage() {
  const { data: summary, error, isLoading } = useDashboardSummary();

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1 p-4 space-y-4">
        {isLoading && (
          <p className="text-center text-muted-foreground">Loading...</p>
        )}
        {error && (
          <p className="text-center text-red-500">
            Failed to load dashboard: {error.message}
          </p>
        )}
        {summary && (
          <>
            <SummaryCards summary={summary} />
            <div className="grid gap-4 md:grid-cols-3">
              <div className="md:col-span-2 space-y-4">
                <h2 className="text-sm font-medium text-muted-foreground">
                  Traders
                </h2>
                <div className="grid gap-4 sm:grid-cols-2">
                  {summary.traders.map((trader) => (
                    <TraderCard key={trader.id} trader={trader} />
                  ))}
                </div>
              </div>
              <div>
                <MarketWatch />
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
