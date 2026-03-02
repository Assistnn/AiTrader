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
import { getPairOptions } from "@/constants/pairs";
import { formatPct, formatDateJst } from "@/lib/utils";
import { apiClient } from "@/lib/api";
import type { BacktestRun, BacktestMetrics } from "@/types/api";

const statusLabels: Record<string, string> = {
  completed: "完了",
  failed: "失敗",
  running: "実行中",
  pending: "待機中",
};

function MetricsPanel({ metrics }: { metrics: BacktestMetrics }) {
  const items = [
    { label: "総取引数", value: String(metrics.totalTrades) },
    { label: "勝率", value: formatPct(metrics.winRate * 100) },
    { label: "プロフィットファクター", value: metrics.profitFactor.toFixed(2) },
    { label: "最大ドローダウン", value: formatPct(metrics.maxDrawdownPct) },
    { label: "シャープレシオ", value: metrics.sharpeRatio.toFixed(2) },
    { label: "平均RR比率", value: metrics.avgRrRatio.toFixed(2) },
    { label: "合計損益率", value: formatPct(metrics.totalPnlPct) },
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
      <Badge variant={statusVariant}>
        {statusLabels[run.status] || run.status}
      </Badge>
      {run.metrics && (
        <>
          <span className="ml-auto w-24 text-right tabular-nums">
            {run.metrics.totalTrades} 取引
          </span>
          <span className="w-24 text-right tabular-nums">
            勝率 {formatPct(run.metrics.winRate * 100)}
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
              <CardTitle className="text-base">新規バックテスト</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <label className="text-xs font-medium">トレーダー</label>
                <Select
                  value={form.traderId}
                  options={
                    traders?.map((t) => ({
                      value: String(t.id),
                      label: t.traderName,
                    })) || []
                  }
                  onChange={(e) => {
                    const tid = e.target.value;
                    const traderType =
                      traders?.find((t) => String(t.id) === tid)?.tradeType ||
                      "FX";
                    const defaultPair = getPairOptions(traderType)[0]?.value || "USD_JPY";
                    setForm({ ...form, traderId: tid, pair: defaultPair });
                  }}
                />
              </div>
              <div>
                <label className="text-xs font-medium">通貨ペア</label>
                <Select
                  value={form.pair}
                  options={getPairOptions(
                    traders?.find((t) => String(t.id) === form.traderId)
                      ?.tradeType || "FX"
                  )}
                  onChange={(e) => setForm({ ...form, pair: e.target.value })}
                />
              </div>
              <div>
                <label className="text-xs font-medium">時間足</label>
                <Select
                  value={form.timeframe}
                  options={[
                    { value: "M5", label: "5分" },
                    { value: "M15", label: "15分" },
                    { value: "H1", label: "1時間" },
                  ]}
                  onChange={(e) =>
                    setForm({ ...form, timeframe: e.target.value })
                  }
                />
              </div>
              <div>
                <label className="text-xs font-medium">開始日</label>
                <Input
                  type="date"
                  value={form.startDate}
                  onChange={(e) =>
                    setForm({ ...form, startDate: e.target.value })
                  }
                />
              </div>
              <div>
                <label className="text-xs font-medium">終了日</label>
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
                {creating ? "実行中..." : "バックテスト実行"}
              </Button>
            </CardContent>
          </Card>

          {/* Right: Results */}
          <div className="md:col-span-2 space-y-4">
            {selected?.metrics && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">
                    結果: {selected.pair} {selected.timeframe}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <MetricsPanel metrics={selected.metrics} />
                </CardContent>
              </Card>
            )}

            <Card>
              <CardHeader>
                <CardTitle className="text-base">バックテスト履歴</CardTitle>
              </CardHeader>
              <CardContent>
                {(() => {
                  const items = backtests?.data ?? [];
                  const totalPages = backtests?.pagination?.totalPages ?? 1;
                  return (
                    <>
                      {items.map((run) => (
                        <BacktestRow
                          key={run.id}
                          run={run}
                          onSelect={setSelected}
                        />
                      ))}
                      {items.length === 0 && (
                        <p className="py-4 text-center text-sm text-muted-foreground">
                          バックテスト履歴がありません
                        </p>
                      )}
                      {totalPages > 1 && (
                        <div className="flex items-center justify-center gap-2 pt-3">
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={page <= 1}
                            onClick={() => setPage(page - 1)}
                          >
                            前へ
                          </Button>
                          <span className="text-sm text-muted-foreground">
                            {page} / {totalPages}
                          </span>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={page >= totalPages}
                            onClick={() => setPage(page + 1)}
                          >
                            次へ
                          </Button>
                        </div>
                      )}
                    </>
                  );
                })()}
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}
