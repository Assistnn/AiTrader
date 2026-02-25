/**
 * WebSocket hook for real-time data.
 * Reference: 10_フロントエンドアーキテクチャ, 08_API仕様
 */

"use client";

import { useEffect, useRef } from "react";
import { TradingWebSocket } from "@/lib/ws";
import { useDashboardStore } from "@/stores/dashboardStore";
import { useTraderStore } from "@/stores/traderStore";
import { useAlertStore } from "@/stores/alertStore";
import type { WsPriceMessage, WsTraderUpdateMessage, WsAlertMessage } from "@/types/api";

export function useWebSocket(token: string | null) {
  const wsRef = useRef<TradingWebSocket | null>(null);
  const updatePrice = useDashboardStore((s) => s.updatePrice);
  const updateTrader = useTraderStore((s) => s.updateTrader);
  const addAlert = useAlertStore((s) => s.addAlert);

  useEffect(() => {
    if (!token) return;

    const ws = new TradingWebSocket(token);
    wsRef.current = ws;

    ws.onMessage("prices", (msg) => {
      const p = msg as WsPriceMessage;
      updatePrice({
        pair: p.pair,
        bid: p.bid,
        ask: p.ask,
        timestamp: p.timestamp,
      });
    });

    ws.onMessage("trader_updates", (msg) => {
      const t = msg as WsTraderUpdateMessage;
      updateTrader(t.traderId, t.data as Record<string, unknown>);
    });

    ws.onMessage("alerts", (msg) => {
      const a = msg as WsAlertMessage;
      addAlert({
        id: String(Date.now()),
        type: a.type as "safeguard" | "pipeline" | "trade" | "system",
        message: String(a.data.message || ""),
        severity: (a.data.severity as "info" | "warning" | "error") || "info",
        timestamp: new Date().toISOString(),
        read: false,
      });
    });

    ws.connect();

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [token, updatePrice, updateTrader, addAlert]);
}
