"use client";

import { useState, useRef, useEffect } from "react";
import { BarChart3, Maximize2, Columns2, Grid2x2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme } from "next-themes";
import { apiClient } from "@/lib/api";
import { useTraders } from "@/hooks/useDashboard";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type Time,
  ColorType,
} from "lightweight-charts";

type GridLayout = 1 | 2 | 4;

const TIMEFRAMES = [
  { value: "M15", label: "15分" },
  { value: "H1", label: "1時間" },
  { value: "H4", label: "4時間" },
  { value: "D1", label: "日足" },
];

interface OhlcvApiItem {
  t: string;
  o: number;
  h: number;
  l: number;
  c: number;
  v: number;
}

/** API response → lightweight-charts CandlestickData */
function toCandles(items: OhlcvApiItem[]): CandlestickData[] {
  return items.map((d) => ({
    time: (Math.floor(new Date(d.t).getTime() / 1000)) as Time,
    open: d.o,
    high: d.h,
    low: d.l,
    close: d.c,
  }));
}

function getChartColors(isDark: boolean) {
  return {
    background: isDark ? "#1a1a2e" : "#ffffff",
    text: isDark ? "#a0a0b0" : "#666666",
    grid: isDark ? "#2a2a3e" : "#f0f0f0",
    upColor: isDark ? "#26a69a" : "#089981",
    downColor: isDark ? "#ef5350" : "#f23645",
  };
}

function formatPairLabel(pair: string): string {
  return pair.replace("_", "/");
}

interface PairOption {
  value: string;
  label: string;
}

/** Extract unique pairs from trader list */
function usePairOptions(): PairOption[] {
  const { data: traders } = useTraders();
  if (!traders || traders.length === 0) return [];
  const seen = new Set<string>();
  const options: PairOption[] = [];
  for (const t of traders) {
    const pair = t.symbols?.[0];
    if (pair && !seen.has(pair)) {
      seen.add(pair);
      options.push({ value: pair, label: formatPairLabel(pair) });
    }
  }
  return options;
}

interface ChartInstanceProps {
  pair: string;
  timeframe: string;
  isDark: boolean;
}

function ChartInstance({ pair, timeframe, isDark }: ChartInstanceProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [hasData, setHasData] = useState(true);

  useEffect(() => {
    if (!containerRef.current) return;

    setHasData(true);
    const colors = getChartColors(isDark);
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: colors.background },
        textColor: colors.text,
      },
      grid: {
        vertLines: { color: colors.grid },
        horzLines: { color: colors.grid },
      },
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
      timeScale: { timeVisible: true, secondsVisible: false },
    });

    const series = chart.addCandlestickSeries({
      upColor: colors.upColor,
      downColor: colors.downColor,
      borderUpColor: colors.upColor,
      borderDownColor: colors.downColor,
      wickUpColor: colors.upColor,
      wickDownColor: colors.downColor,
    });

    chartRef.current = chart;
    seriesRef.current = series;

    let cancelled = false;
    (async () => {
      try {
        const items = await apiClient.get<OhlcvApiItem[]>(
          `/api/v1/charts/ohlcv?pair=${pair}&timeframe=${timeframe}&limit=200`
        );
        if (!cancelled && items.length > 0) {
          series.setData(toCandles(items));
          chart.timeScale().fitContent();
        } else if (!cancelled) {
          setHasData(false);
        }
      } catch {
        if (!cancelled) {
          setHasData(false);
        }
      }
    })();

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    };

    const observer = new ResizeObserver(handleResize);
    observer.observe(containerRef.current);

    return () => {
      cancelled = true;
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [pair, timeframe, isDark]);

  if (!hasData) {
    return (
      <div className="flex h-full w-full items-center justify-center text-muted-foreground">
        <div className="text-center">
          <BarChart3 className="mx-auto mb-2 h-8 w-8 opacity-50" />
          <p className="text-sm">データがありません</p>
          <p className="text-xs mt-1">トレーダーを起動するとチャートデータが取得されます</p>
        </div>
      </div>
    );
  }

  return <div ref={containerRef} className="h-full w-full" />;
}

/** Single chart pane with its own pair/timeframe selectors */
function ChartPane({
  pairs,
  defaultPair,
  defaultTimeframe,
  isDark,
  height,
}: {
  pairs: PairOption[];
  defaultPair: string;
  defaultTimeframe: string;
  isDark: boolean;
  height: string;
}) {
  const [pair, setPair] = useState(defaultPair);
  const [timeframe, setTimeframe] = useState(defaultTimeframe);

  // Update pair if defaultPair changes (e.g. trader list updated)
  useEffect(() => {
    if (pairs.length > 0 && !pairs.find((p) => p.value === pair)) {
      setPair(pairs[0].value);
    }
  }, [pairs, pair]);

  return (
    <div className="flex flex-col rounded-lg border bg-card">
      <div style={{ height }} className="relative">
        {pairs.length > 0 ? (
          <ChartInstance
            key={`${pair}-${timeframe}`}
            pair={pair}
            timeframe={timeframe}
            isDark={isDark}
          />
        ) : (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            <div className="text-center">
              <BarChart3 className="mx-auto mb-2 h-8 w-8 opacity-50" />
              <p className="text-sm">トレーダーを作成してください</p>
            </div>
          </div>
        )}
      </div>
      {/* Per-pane selectors below chart */}
      <div className="flex items-center gap-2 border-t px-3 py-1.5">
        <BarChart3 className="h-3.5 w-3.5 text-muted-foreground" />
        <select
          className="rounded border bg-background px-2 py-0.5 text-xs"
          value={pair}
          onChange={(e) => setPair(e.target.value)}
          disabled={pairs.length === 0}
        >
          {pairs.length === 0 && <option value="">--</option>}
          {pairs.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </select>
        <select
          className="rounded border bg-background px-2 py-0.5 text-xs"
          value={timeframe}
          onChange={(e) => setTimeframe(e.target.value)}
        >
          {TIMEFRAMES.map((tf) => (
            <option key={tf.value} value={tf.value}>
              {tf.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

export function ChartPanel() {
  const [layout, setLayout] = useState<GridLayout>(1);
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  const pairs = usePairOptions();

  const defaultPairs = pairs.length > 0
    ? pairs.map((p) => p.value)
    : [];

  const paneCount = layout;
  const chartHeight = layout === 1 ? "400px" : "280px";

  const layoutButtons: { value: GridLayout; label: string; icon: React.ReactNode }[] = [
    { value: 1, label: "1画面", icon: <Maximize2 className="h-3.5 w-3.5" /> },
    { value: 2, label: "2画面", icon: <Columns2 className="h-3.5 w-3.5" /> },
    { value: 4, label: "4画面", icon: <Grid2x2 className="h-3.5 w-3.5" /> },
  ];

  return (
    <div>
      {/* Header toolbar */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">チャート表示</span>
        </div>
        <div className="flex rounded-md border">
          {layoutButtons.map((l) => (
            <button
              key={l.value}
              onClick={() => setLayout(l.value)}
              className={cn(
                "flex items-center gap-1 px-2.5 py-1 text-xs",
                layout === l.value
                  ? "bg-foreground text-background"
                  : "text-muted-foreground hover:bg-accent"
              )}
            >
              {l.icon}
              {l.label}
            </button>
          ))}
        </div>
      </div>

      {/* Chart panes */}
      <div
        className={cn(
          layout === 2 && "grid grid-cols-2 gap-3",
          layout === 4 && "grid grid-cols-2 gap-3"
        )}
      >
        {Array.from({ length: paneCount }, (_, i) => (
          <ChartPane
            key={`pane-${i}-${layout}`}
            pairs={pairs}
            defaultPair={defaultPairs[i % defaultPairs.length] ?? ""}
            defaultTimeframe="M15"
            isDark={isDark}
            height={chartHeight}
          />
        ))}
      </div>
    </div>
  );
}
