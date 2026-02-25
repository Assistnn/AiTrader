/**
 * SWR hooks for dashboard data fetching.
 * Reference: 10_フロントエンドアーキテクチャ
 */

import useSWR from "swr";
import { fetcher } from "@/lib/api";
import type { DashboardSummary, Trader, PaginatedResponse, TradeRecord } from "@/types/api";

/** Dashboard summary with 5-second refresh. */
export function useDashboardSummary() {
  return useSWR<DashboardSummary>("/api/v1/dashboard/summary", fetcher, {
    refreshInterval: 5000,
  });
}

/** Trader list. */
export function useTraders() {
  return useSWR<Trader[]>("/api/v1/traders", fetcher);
}

/** Trade history with pagination. */
export function useTradeHistory(page: number, perPage = 20) {
  return useSWR<PaginatedResponse<TradeRecord>>(
    `/api/v1/history?page=${page}&perPage=${perPage}`,
    fetcher
  );
}
