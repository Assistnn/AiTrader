/**
 * SWR hooks for backtest data fetching.
 * Reference: 09_バックテストシミュレーション
 */

import useSWR from "swr";
import { fetcher, paginatedFetcher } from "@/lib/api";
import type { PaginatedResponse, BacktestRun } from "@/types/api";

export function useBacktestList(page: number, perPage = 20) {
  return useSWR<PaginatedResponse<BacktestRun>>(
    `/api/v1/backtests?page=${page}&perPage=${perPage}`,
    paginatedFetcher<BacktestRun>
  );
}

export function useBacktestDetail(id: number | null) {
  return useSWR<BacktestRun>(
    id ? `/api/v1/backtests/${id}` : null,
    fetcher
  );
}
