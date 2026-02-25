/** API response wrapper. Reference: 08_API仕様 */
export interface ApiResponse<T> {
  status: "ok" | "error";
  data?: T;
  error?: { code: string; message: string };
}

/** Pagination response. */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  perPage: number;
  totalPages: number;
}

/** Trader summary (lowerCamelCase). Reference: 08_API仕様 */
export interface Trader {
  id: number;
  name: string;
  tradeType: "fx" | "crypto";
  pair: string;
  status: "running" | "stopped" | "error";
  capital: number;
  lotSize: number;
  strategyText: string;
  pipelineState?: PipelineState;
  guardState?: GuardStateIndicator;
  dailyPnl: number;
  monthlyPnl: number;
}

export interface PipelineState {
  m1Trend: "UP" | "DOWN" | "NEUTRAL";
  m2Setup: string;
  lastExecution: string;
}

export interface GuardStateIndicator {
  status: "normal" | "warning" | "halted";
  blockingGuards: string[];
}

/** Dashboard summary. Reference: 01_画面仕様 */
export interface DashboardSummary {
  traders: Trader[];
  totalDailyPnl: number;
  totalMonthlyPnl: number;
  activePositions: number;
  prices: Record<string, PriceQuote>;
}

export interface PriceQuote {
  pair: string;
  bid: number;
  ask: number;
  timestamp: string;
}

/** Trade history record. */
export interface TradeRecord {
  id: number;
  traderId: number;
  traderName: string;
  pair: string;
  side: "BUY" | "SELL";
  amount: number;
  entryPrice: number;
  exitPrice: number;
  entryTimestamp: string;
  exitTimestamp: string;
  realizedPnl: number;
  realizedPnlPips: number;
  rrRatio: number;
  exitReason: string;
  pipelineLogs?: PipelineLogSummary;
}

export interface PipelineLogSummary {
  executionId: string;
  m1: StageResult;
  m2: StageResult;
  m3: StageResult;
  m4?: StageResult;
  guardState: { status: string; blockingGuards: string[] };
}

export interface StageResult {
  result: Record<string, unknown>;
  confidence: number;
  reasonCodes: string[];
  elapsedMs: number;
}

/** Backtest types. Reference: 09_バックテストシミュレーション */
export interface BacktestRun {
  id: number;
  traderId: number;
  pair: string;
  timeframe: string;
  startDate: string;
  endDate: string;
  status: "pending" | "running" | "completed" | "failed";
  metrics?: BacktestMetrics;
  createdAt: string;
}

export interface BacktestMetrics {
  totalPnl: number;
  totalPnlPct: number;
  totalTrades: number;
  winRate: number;
  profitFactor: number;
  maxDrawdownPct: number;
  sharpeRatio: number;
  avgRrRatio: number;
}

/** Model stage config. Reference: 04_判断パイプライン */
export interface ModelStageConfig {
  enabled: boolean;
  mode: "rule" | "aiAssist" | "aiFull";
  timeframes: string[];
  params: Record<string, unknown>;
}

/** WebSocket message types. Reference: 08_API仕様 */
export interface WsMessage {
  channel: "prices" | "trader_updates" | "alerts" | "pipeline_status";
  [key: string]: unknown;
}

export interface WsPriceMessage extends WsMessage {
  channel: "prices";
  pair: string;
  bid: number;
  ask: number;
  timestamp: string;
}

export interface WsTraderUpdateMessage extends WsMessage {
  channel: "trader_updates";
  traderId: number;
  type: string;
  data: Record<string, unknown>;
}

export interface WsAlertMessage extends WsMessage {
  channel: "alerts";
  type: string;
  data: Record<string, unknown>;
}
