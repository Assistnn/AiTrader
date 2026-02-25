/**
 * WebSocket client with exponential backoff reconnection.
 * Reference: 08_API仕様, 10_フロントエンドアーキテクチャ
 *
 * 4 channels: prices, trader_updates, alerts, pipeline_status
 */

import type { WsMessage } from "@/types/api";

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

type MessageHandler = (msg: WsMessage) => void;

export class TradingWebSocket {
  private ws: WebSocket | null = null;
  private url: string;
  private handlers: Map<string, Set<MessageHandler>> = new Map();
  private reconnectAttempt = 0;
  private maxReconnectDelay = 60_000; // 60s max
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private closed = false;

  constructor(token: string) {
    this.url = `${WS_BASE}/api/v1/ws?token=${token}`;
  }

  connect() {
    if (this.closed) return;
    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.reconnectAttempt = 0;
      };

      this.ws.onmessage = (event) => {
        try {
          const msg: WsMessage = JSON.parse(event.data);
          const channelHandlers = this.handlers.get(msg.channel);
          if (channelHandlers) {
            channelHandlers.forEach((h) => h(msg));
          }
        } catch {
          // Ignore parse errors
        }
      };

      this.ws.onclose = () => {
        if (!this.closed) this.scheduleReconnect();
      };

      this.ws.onerror = () => {
        this.ws?.close();
      };
    } catch {
      this.scheduleReconnect();
    }
  }

  subscribe(channel: string, pairs?: string[], traderIds?: number[]) {
    const msg: Record<string, unknown> = { action: "subscribe", channel };
    if (pairs) msg.pairs = pairs;
    if (traderIds) msg.traderIds = traderIds;
    this.send(msg);
  }

  unsubscribe(channel: string) {
    this.send({ action: "unsubscribe", channel });
  }

  onMessage(channel: string, handler: MessageHandler) {
    if (!this.handlers.has(channel)) {
      this.handlers.set(channel, new Set());
    }
    this.handlers.get(channel)!.add(handler);
    return () => {
      this.handlers.get(channel)?.delete(handler);
    };
  }

  close() {
    this.closed = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.handlers.clear();
  }

  private send(data: unknown) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  private scheduleReconnect() {
    // Exponential backoff: 1s, 2s, 4s, 8s, ... max 60s
    const delay = Math.min(
      1000 * Math.pow(2, this.reconnectAttempt),
      this.maxReconnectDelay
    );
    this.reconnectAttempt++;
    this.reconnectTimer = setTimeout(() => this.connect(), delay);
  }
}
