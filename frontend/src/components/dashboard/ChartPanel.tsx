"use client";

import { useState, useRef, useEffect } from "react";
import { BarChart3 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme } from "next-themes";
import { apiClient } from "@/lib/api";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type Time,
  ColorType,
} from "lightweight-charts";

type GridLayout = 1 | 2 | 4;

const PAIRS = [
  { value: "USD_JPY", label: "USD/JPY" },
  { value: "EUR_JPY", label: "EUR/JPY" },
  { value: "BTC_JPY", label: "BTC/JPY" },
];

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

/** Fallback mock data when API is unavailable */
function generateMockOhlc(pair: string, count = 100): CandlestickData[] {
  const data: CandlestickData[] = [];
  const basePrice = pair === "BTC_JPY" ? 6500000 : pair === "EUR_JPY" ? 162.5 : 150.0;
  const volatility = pair === "BTC_JPY" ? 50000 : 0.5;
  const now = Math.floor(Date.now() / 1000);
  const interval = 900;

  let price = basePrice;
  for (let i = 0; i < count; i++) {
    const time = (now - (count - i) * interval) as Time;
    const change = (Math.random() - 0.48) * volatility;
    const open = price;
    const close = price + change;
    const high = Math.max(open, close) + Math.random() * volatility * 0.5;
    const low = Math.min(open, close) - Math.random() * volatility * 0.5;
    data.push({ time, open, high, low, close });
    price = close;
  }
  return data;
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

interface ChartInstanceProps {
  pair: string;
  timeframe: string;
  isDark: boolean;
}

function ChartInstance({ pair, timeframe, isDark }: ChartInstanceProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

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

    // Fetch data from API, fall back to mock on error
    let cancelled = false;
    (async () => {
      try {
        const items = await apiClient.get<OhlcvApiItem[]>(
          `/api/v1/charts/ohlcv?pair=${pair}&timeframe=${timeframe}&limit=200`
        );
        if (!cancelled && items.length > 0) {
          series.setData(toCandles(items));
        } else if (!cancelled) {
          series.setData(generateMockOhlc(pair));
        }
      } catch {
        if (!cancelled) {
          series.setData(generateMockOhlc(pair));
        }
      }
      if (!cancelled) {
        chart.timeScale().fitContent();
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

  return <div ref={containerRef} className="h-full w-full min-h-[200px]" />;
}

export function ChartPanel() {
  const [layout, setLayout] = useState<GridLayout>(1);
  const [selectedPair, setSelectedPair] = useState("USD_JPY");
  const [selectedTimeframe, setSelectedTimeframe] = useState("M15");
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  // For multi-chart layout, assign different pairs
  const chartPairs = layout === 1
    ? [selectedPair]
    : layout === 2
    ? [selectedPair, PAIRS.find((p) => p.value !== selectedPair)?.value || "EUR_JPY"]
    : PAIRS.slice(0, 4).map((p) => p.value);

  const layouts: { value: GridLayout; label: string }[] = [
    { value: 1, label: "1" },
    { value: 2, label: "2" },
    { value: 4, label: "4" },
  ];

  return (
    <div className="flex flex-1 flex-col rounded-lg border bg-card">
      {/* Chart toolbar */}
      <div className="flex items-center justify-between border-b px-4 py-2">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">チャート</span>
        </div>
        <div className="flex items-center gap-2">
          <select
            className="rounded-md border bg-background px-2 py-1 text-xs"
            value={selectedPair}
            onChange={(e) => setSelectedPair(e.target.value)}
          >
            {PAIRS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
          <select
            className="rounded-md border bg-background px-2 py-1 text-xs"
            value={selectedTimeframe}
            onChange={(e) => setSelectedTimeframe(e.target.value)}
          >
            {TIMEFRAMES.map((tf) => (
              <option key={tf.value} value={tf.value}>
                {tf.label}
              </option>
            ))}
          </select>
          <div className="flex rounded-md border">
            {layouts.map((l) => (
              <button
                key={l.value}
                onClick={() => setLayout(l.value)}
                className={cn(
                  "px-2 py-1 text-xs",
                  layout === l.value
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:bg-accent"
                )}
              >
                {l.label}画面
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Chart area */}
      <div
        className={cn(
          "flex-1 p-2",
          layout === 2 && "grid grid-cols-2 gap-2",
          layout === 4 && "grid grid-cols-2 grid-rows-2 gap-2"
        )}
      >
        {chartPairs.map((pair, i) => (
          <div key={`${pair}-${i}-${layout}-${selectedTimeframe}`} className="min-h-[200px]">
            <ChartInstance pair={pair} timeframe={selectedTimeframe} isDark={isDark} />
          </div>
        ))}
      </div>
    </div>
  );
}
