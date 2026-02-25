"use client";

import { useState } from "react";
import { Header } from "@/components/common/Header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useBacktestList } from "@/hooks/useBacktest";
import { useTraders } from "@/hooks/useDashboard";
import { formatPct, formatDateJst } from "@/lib/utils";
import { apiClient } from "@/lib/api";
import type { BacktestRun, BacktestMetrics } from "@/types/api";

function MetricsPanel({ metrics }: { metrics: BacktestMetrics }) {
  const items = [
    { label: "Total Trades", value: String(metrics.totalTrades) },
    { label: "Win Rate", value: formatPct(metrics.winRate * 100) },
    { label: "Profit Factor", value: metrics.profitFactor.toFixed(2) },
    { label: "Max Drawdown", value: formatPct(metrics.maxDrawdownPct) },
    { label: "Sharpe Ratio", value: metrics.sharpeRatio.toFixed(2) },
    { label: "Avg RR Ratio", value: metrics.avgRrRatio.toFixed(2) },
    { label: "Total P&L %", value: formatPct(metrics.totalPnlPct) },
  ];

  return (
    <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
      {items.map((item) => (
        <div key={item.label} className="rounded border p-2">
          <p className="text-xs text-muted-foreground">{item.label}</p>
          <p className="text-sm font-bold tabular-nums">{item.value}</p>
        </div>
      ))}
    </div>
  );
}

function BacktestRow({
  run,
  onSelect,
}: {
  run: BacktestRun;
  onSelect: (r: BacktestRun) => void;
}) {
  const statusVariant =
    run.status === "completed"
      ? "success"
      : run.status === "failed"
      ? "destructive"
      : run.status === "running"
      ? "warning"
      : "secondary";

  return (
    <button
      className="flex w-full items-center gap-3 border-b px-4 py-2 text-sm hover:bg-accent/50 last:border-b-0"
      onClick={() => onSelect(run)}
    >
      <span className="w-28 text-xs text-muted-foreground">
        {formatDateJst(run.createdAt)}
      </span>
      <span className="w-20">{run.pair}</span>
      <span className="w-12">{run.timeframe}</span>
      <Badge variant={statusVariant}>{run.status}</Badge>
      {run.metrics && (
        <>
          <span className="ml-auto w-20 text-right tabular-nums">
            {run.metrics.totalTrades} trades
          </span>
          <span className="w-20 text-right tabular-nums">
            {formatPct(run.metrics.winRate * 100)} WR
          </span>
        </>
      )}
    </button>
  );
}

export function BacktestPage() {
  const [page, setPage] = useState(1);
  const { data: backtests, mutate } = useBacktestList(page);
  const { data: traders } = useTraders();
  const [selected, setSelected] = useState<BacktestRun | null>(null);
  const [creating, setCreating] = useState(false);

  // New backtest form state
  const [form, setForm] = useState({
    traderId: "",
    pair: "USD_JPY",
    timeframe: "M15",
    startDate: "",
    endDate: "",
  });

  const handleCreate = async () => {
    if (!form.traderId || !form.startDate || !form.endDate) return;
    setCreating(true);
    try {
      await apiClient.post("/api/v1/backtests", {
        traderId: Number(form.traderId),
        pair: form.pair,
        timeframe: form.timeframe,
        startDate: form.startDate,
        endDate: form.endDate,
        useCurrentConfig: true,
      });
      await mutate();
    } catch {
      // error handled by apiClient
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1 p-4 space-y-4">
        <div className="grid gap-4 md:grid-cols-3">
          {/* Left: Run form */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">New Backtest</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <label className="text-xs font-medium">Trader</label>
                <Select
                  value={form.traderId}
                  options={
                    traders?.map((t) => ({
                      value: String(t.id),
                      label: t.name,
                    })) || []
                  }
                  onChange={(e) =>
                    setForm({ ...form, traderId: e.target.value })
                  }
                />
              </div>
              <div>
                <label className="text-xs font-medium">Pair</label>
                <Select
                  value={form.pair}
                  options={[
                    { value: "USD_JPY", label: "USD/JPY" },
                    { value: "EUR_JPY", label: "EUR/JPY" },
                    { value: "GBP_JPY", label: "GBP/JPY" },
                  ]}
                  onChange={(e) => setForm({ ...form, pair: e.target.value })}
                />
              </div>
              <div>
                <label className="text-xs font-medium">Timeframe</label>
                <Select
                  value={form.timeframe}
                  options={[
                    { value: "M5", label: "M5" },
                    { value: "M15", label: "M15" },
                    { value: "H1", label: "H1" },
                  ]}
                  onChange={(e) =>
                    setForm({ ...form, timeframe: e.target.value })
                  }
                />
              </div>
              <div>
                <label className="text-xs font-medium">Start Date</label>
                <Input
                  type="date"
                  value={form.startDate}
                  onChange={(e) =>
                    setForm({ ...form, startDate: e.target.value })
                  }
                />
              </div>
              <div>
                <label className="text-xs font-medium">End Date</label>
                <Input
                  type="date"
                  value={form.endDate}
                  onChange={(e) =>
                    setForm({ ...form, endDate: e.target.value })
                  }
                />
              </div>
              <Button
                className="w-full"
                onClick={handleCreate}
                disabled={creating}
              >
                {creating ? "Running..." : "Run Backtest"}
              </Button>
            </CardContent>
          </Card>

          {/* Right: Results */}
          <div className="md:col-span-2 space-y-4">
            {selected?.metrics && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">
                    Results: {selected.pair} {selected.timeframe}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <MetricsPanel metrics={selected.metrics} />
                </CardContent>
              </Card>
            )}

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Backtest History</CardTitle>
              </CardHeader>
              <CardContent>
                {backtests?.items.map((run) => (
                  <BacktestRow
                    key={run.id}
                    run={run}
                    onSelect={setSelected}
                  />
                ))}
                {backtests && backtests.totalPages > 1 && (
                  <div className="flex items-center justify-center gap-2 pt-3">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page <= 1}
                      onClick={() => setPage(page - 1)}
                    >
                      Prev
                    </Button>
                    <span className="text-sm text-muted-foreground">
                      {page} / {backtests.totalPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page >= backtests.totalPages}
                      onClick={() => setPage(page + 1)}
                    >
                      Next
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}
