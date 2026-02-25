/**
 * Dashboard store: summary data and real-time prices.
 * Reference: 10_フロントエンドアーキテクチャ
 */

import { create } from "zustand";
import type { DashboardSummary, PriceQuote } from "@/types/api";

interface DashboardState {
  summary: DashboardSummary | null;
  prices: Record<string, PriceQuote>;
  isLoading: boolean;
  error: string | null;
  setSummary: (summary: DashboardSummary) => void;
  updatePrice: (price: PriceQuote) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  summary: null,
  prices: {},
  isLoading: false,
  error: null,
  setSummary: (summary) => set({ summary, isLoading: false, error: null }),
  updatePrice: (price) =>
    set((state) => ({
      prices: { ...state.prices, [price.pair]: price },
    })),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error, isLoading: false }),
}));
