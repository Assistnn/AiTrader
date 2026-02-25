/**
 * Trader store: trader list and CRUD operations.
 * Reference: 10_フロントエンドアーキテクチャ
 */

import { create } from "zustand";
import type { Trader } from "@/types/api";

interface TraderState {
  traders: Trader[];
  activeTrader: Trader | null;
  setTraders: (traders: Trader[]) => void;
  setActiveTrader: (trader: Trader | null) => void;
  updateTrader: (id: number, updates: Partial<Trader>) => void;
}

export const useTraderStore = create<TraderState>((set) => ({
  traders: [],
  activeTrader: null,
  setTraders: (traders) => set({ traders }),
  setActiveTrader: (activeTrader) => set({ activeTrader }),
  updateTrader: (id, updates) =>
    set((state) => ({
      traders: state.traders.map((t) =>
        t.id === id ? { ...t, ...updates } : t
      ),
      activeTrader:
        state.activeTrader?.id === id
          ? { ...state.activeTrader, ...updates }
          : state.activeTrader,
    })),
}));
