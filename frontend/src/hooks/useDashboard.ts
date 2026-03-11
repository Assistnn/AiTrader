/**
 * SWR hooks for dashboard data fetching.
 * Reference: 10_フロントエンドアーキテクチャ
 */

import useSWR from "swr";
import { fetcher, paginatedFetcher } from "@/lib/api";
import type { DashboardSummary, Trader, TradeRecord, PaginatedResponse, ModelStageConfig } from "@/types/api";

/** Dashboard summary with 5-second refresh. */
export function useDashboardSummary() {
  return useSWR<DashboardSummary>("/api/v1/dashboard/summary", fetcher, {
    refreshInterval: 5000,
    keepPreviousData: true,
    revalidateOnFocus: false,
    dedupingInterval: 3000,
  });
}

/** Trader list (full detail). */
export function useTraders() {
  return useSWR<Trader[]>("/api/v1/traders", fetcher, {
    keepPreviousData: true,
    revalidateOnFocus: false,
  });
}

/** Model stage configs for a trader. */
export function useModelStages(traderId: number | null) {
  return useSWR<ModelStageConfig[]>(
    traderId ? `/api/v1/traders/${traderId}/model-stages` : null,
    fetcher,
    { revalidateOnFocus: false },
  );
}

/** Safeguard config for a trader. */
export function useSafeguardConfig(traderId: number | null) {
  return useSWR<{ id: number; traderId: number; configJson: Record<string, unknown> }>(
    traderId ? `/api/v1/traders/${traderId}/safeguards` : null,
    fetcher,
    { revalidateOnFocus: false },
  );
}

/** Trade history with pagination metadata. */
export function useTradeHistory(page: number, perPage = 20) {
  return useSWR<PaginatedResponse<TradeRecord>>(
    `/api/v1/history?page=${page}&perPage=${perPage}`,
    paginatedFetcher<TradeRecord>
  );
}
