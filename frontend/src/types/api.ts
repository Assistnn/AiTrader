/** API response wrapper. Reference: 08_API仕様 */
export interface ApiResponse<T> {
  status: "ok" | "error";
  data?: T;
  error?: { code: string; message: string };
}

/** Pagination metadata from backend. Reference: 08_API仕様 Section 2-4 */
export interface Pagination {
  page: number;
  perPage: number;
  totalItems: number;
  totalPages: number;
}

/** Paginated response from backend. */
export interface PaginatedResponse<T> {
  data: T[];
  pagination: Pagination;
}

/** Trader detail (GET /api/v1/traders/{id}). Matches backend TraderResponse. */
export interface Trader {
  id: number;
  traderName: string;
  tradeType: string;
  symbols: string[];
  capitalJpy: number;
  orderUnitLots: number;
  strategyText: string | null;
  status: "running" | "stopped" | "error" | "halted";
  createdAt: string;
}

/** Trader list item (GET /api/v1/traders). Matches backend TraderListItem. */
export interface TraderListItem {
  id: number;
  traderName: string;
  tradeType: string;
  status: string;
  capitalJpy: number;
  createdAt: string;
}

/** Trader summary in dashboard. Matches backend TraderSummary. */
export interface TraderSummary {
  traderId: number;
  traderName: string;
  status: string;
  pnlToday: number;
  openPositions: number;
  pipelineState?: PipelineStateResponse | null;
}

export interface PipelineStateResponse {
  lastM1?: Record<string, unknown> | null;
  lastM2?: Record<string, unknown> | null;
  guardState?: Record<string, unknown> | null;
}

export interface GuardStateIndicator {
  status: "normal" | "warning" | "halted";
  blockingGuards: string[];
}

/** Dashboard summary. Matches backend DashboardSummaryResponse. */
export interface DashboardSummary {
  totalPnlToday: number;
  totalPnlMonth: number;
  activeTraders: number;
  openPositions: number;
  traders: TraderSummary[];
}

export interface PriceQuote {
  pair: string;
  bid: number;
  ask: number;
  timestamp: string;
}

/** Trade history record. Matches backend TradeHistoryItem. */
export interface TradeRecord {
  id: number;
  traderId: number;
  pair: string;
  side: "BUY" | "SELL";
  amount: number | null;
  entryPrice: number | null;
  exitPrice: number | null;
  realizedPnl: number | null;
  realizedPnlPips: number | null;
  rrRatio: number | null;
  exitReason: string | null;
  openedAt: string;
  closedAt: string | null;
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

/** Exchange API config. Reference: 08_API仕様 Section 3-14 */
export interface ExchangeConfig {
  id: number;
  exchangeType: string;
  apiKeyMasked: string;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

/** AI provider config. Reference: 08_API仕様 Section 3-14 */
export interface AiConfig {
  id: number;
  provider: string;
  apiKeyMasked: string;
  defaultModel: string | null;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

/** Account info. Reference: 08_API仕様 Section 3-2 */
export interface AccountInfo {
  id: number;
  email: string;
  displayName: string | null;
  isActive: boolean;
  createdAt: string;
}

/** Cost config (read-only, server-configured). Reference: 14_コスト管理 */
export interface CostConfig {
  dailyTokenLimit: number;
  rateLimitPerTrader: number;
  rateLimitGlobal: number;
  warningThresholdPct: number;
}

/** SMTP config. Reference: 08_API仕様 Section 3-9 */
export interface SmtpConfig {
  host: string | null;
  port: number | null;
  username: string | null;
  useTls: boolean;
  fromAddress: string | null;
}

/** Notification email item. Reference: 08_API仕様 Section 3-9 */
export interface NotificationEmailItem {
  id: number;
  email: string;
  isActive: boolean;
  createdAt: string;
}

/** Daily notification config. Reference: 08_API仕様 Section 3-9 */
export interface DailyNotificationConfig {
  id: number;
  enabled: boolean;
  sendTimeUtc: string | null;
  includePnl: boolean;
  includeTrades: boolean;
  includeGuards: boolean;
  createdAt: string;
  updatedAt: string;
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
