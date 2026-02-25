/**
 * Alert store: WebSocket-driven alerts.
 * Reference: 10_フロントエンドアーキテクチャ
 */

import { create } from "zustand";

export interface Alert {
  id: string;
  type: "safeguard" | "pipeline" | "trade" | "system";
  message: string;
  severity: "info" | "warning" | "error";
  timestamp: string;
  read: boolean;
}

interface AlertState {
  alerts: Alert[];
  unreadCount: number;
  addAlert: (alert: Alert) => void;
  markRead: (id: string) => void;
  markAllRead: () => void;
  clearAlerts: () => void;
}

export const useAlertStore = create<AlertState>((set) => ({
  alerts: [],
  unreadCount: 0,
  addAlert: (alert) =>
    set((state) => ({
      alerts: [alert, ...state.alerts].slice(0, 100),
      unreadCount: state.unreadCount + 1,
    })),
  markRead: (id) =>
    set((state) => ({
      alerts: state.alerts.map((a) => (a.id === id ? { ...a, read: true } : a)),
      unreadCount: Math.max(0, state.unreadCount - 1),
    })),
  markAllRead: () =>
    set((state) => ({
      alerts: state.alerts.map((a) => ({ ...a, read: true })),
      unreadCount: 0,
    })),
  clearAlerts: () => set({ alerts: [], unreadCount: 0 }),
}));
