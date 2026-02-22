# 07. データベーススキーマ設計書

## 1. 概要

本設計書は全テーブル定義、インデックス設計、マルチテナント隔離を定義する。

**技術スタック:**
- DB: PostgreSQL（本番） / SQLite（テスト）
- ORM: SQLAlchemy 2.0
- マイグレーション: Alembic

**【監査1】マルチテナント隔離:**
- 全テーブルに `user_id` カラム必須（users テーブル以外）
- `TenantAwareSession` で全クエリに自動フィルタ

---

## 2. 【監査1】テナント隔離メカニズム

### 2-1. TenantAwareSession

```python
class TenantAwareSession:
    """user_idを自動フィルタするセッション"""

    def __init__(self, session: Session, user_id: int):
        self.session = session
        self.user_id = user_id

    def query(self, model):
        """全クエリにuser_idフィルタを自動付与"""
        base_query = self.session.query(model)
        if hasattr(model, 'user_id'):
            return base_query.filter(model.user_id == self.user_id)
        return base_query
```

### 2-2. レビュー基準

```
- 直接SQLを書く場合も必ずuser_id条件を含むこと
- CIでSQLクエリの静的解析（user_idフィルタの有無チェック）を推奨
```

---

## 3. テーブル一覧

### 3-1. 基本テーブル

**users（ユーザー管理）**
```sql
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    display_name    VARCHAR(100),
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**traders（トレーダー基本設定 T-001〜T-012）**
```sql
CREATE TABLE traders (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    trader_name     VARCHAR(40) NOT NULL,               -- T-001
    trade_type      VARCHAR(10) NOT NULL DEFAULT 'FX',  -- T-002: FX / Crypto
    symbols         JSONB NOT NULL DEFAULT '["USD_JPY"]', -- T-003: array<string>
    capital_jpy     NUMERIC(15,2) NOT NULL DEFAULT 1000000, -- T-004
    order_unit_lots NUMERIC(10,4) NOT NULL DEFAULT 1.0, -- T-005
    strategy_text   TEXT DEFAULT '',                     -- T-006: max 2000文字
    notify_email    VARCHAR(255),                        -- T-007
    notify_on_entry   BOOLEAN DEFAULT true,              -- T-008
    notify_on_stop    BOOLEAN DEFAULT true,              -- T-009
    notify_on_error   BOOLEAN DEFAULT true,              -- T-010
    notify_on_exit    BOOLEAN DEFAULT true,              -- T-011
    notify_on_target  BOOLEAN DEFAULT true,              -- T-012
    is_active       BOOLEAN NOT NULL DEFAULT false,
    status          VARCHAR(20) NOT NULL DEFAULT 'stopped', -- running/stopped/halted
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_traders_user_id ON traders(user_id);
```

**model_stage_configs（4段階モデル設定 M1〜M4+MX, 41項目）**
```sql
CREATE TABLE model_stage_configs (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    trader_id       INTEGER NOT NULL REFERENCES traders(id),
    stage           VARCHAR(10) NOT NULL,  -- m1/m2/m3/m4/mx
    config_json     JSONB NOT NULL,        -- 各段階の設定（APIキー準拠）
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(trader_id, stage)
);
CREATE INDEX idx_msc_user_id ON model_stage_configs(user_id);
CREATE INDEX idx_msc_trader_id ON model_stage_configs(trader_id);
```

**config_json 構造例（m1の場合）:**
```json
{
  "enabled": true,
  "timeframes": ["D1", "H4", "H1"],
  "useTrendDirection": true,
  "useRangeAvoid": true,
  "useVolatility": true,
  "mode": "rule",
  "ai": {
    "provider": "ChatGPT",
    "model": "gpt-4",
    "minConfidence": 70
  }
}
```

**safeguard_configs（セーフガード設定 SG-001〜SG-040）**
```sql
CREATE TABLE safeguard_configs (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    trader_id       INTEGER NOT NULL REFERENCES traders(id),
    config_json     JSONB NOT NULL,    -- 40項目のセーフガード設定
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(trader_id)
);
CREATE INDEX idx_sgc_user_id ON safeguard_configs(user_id);
CREATE INDEX idx_sgc_trader_id ON safeguard_configs(trader_id);
```

### 3-2. 取引テーブル

**positions（保有ポジション）**
```sql
CREATE TABLE positions (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    trader_id       INTEGER NOT NULL REFERENCES traders(id),
    exchange_position_id VARCHAR(100),  -- 取引所側のポジションID
    pair            VARCHAR(20) NOT NULL,
    side            VARCHAR(4) NOT NULL,   -- BUY / SELL
    amount          NUMERIC(15,8) NOT NULL,
    entry_price     NUMERIC(20,8) NOT NULL,
    current_price   NUMERIC(20,8),
    unrealized_pnl  NUMERIC(15,2),
    tp_price        NUMERIC(20,8),
    sl_price        NUMERIC(20,8),
    break_even_applied BOOLEAN DEFAULT false,
    trail_active    BOOLEAN DEFAULT false,
    trail_price     NUMERIC(20,8),
    opened_at       TIMESTAMP NOT NULL,
    execution_id    VARCHAR(36),          -- パイプライン実行ID
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_positions_user_id ON positions(user_id);
CREATE INDEX idx_positions_trader_id ON positions(trader_id);
CREATE INDEX idx_positions_pair ON positions(pair);
```

**trade_history（取引履歴）**
```sql
CREATE TABLE trade_history (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    trader_id       INTEGER NOT NULL REFERENCES traders(id),
    pair            VARCHAR(20) NOT NULL,
    side            VARCHAR(4) NOT NULL,
    amount          NUMERIC(15,8) NOT NULL,
    entry_price     NUMERIC(20,8) NOT NULL,
    exit_price      NUMERIC(20,8),
    realized_pnl    NUMERIC(15,2),
    realized_pnl_pips NUMERIC(10,2),
    rr_ratio        NUMERIC(5,2),          -- 実現RR比
    tp_pips         NUMERIC(10,2),
    sl_pips         NUMERIC(10,2),
    exit_reason     VARCHAR(50),           -- tp/sl/manual/safeguard/max_hold/trail
    execution_id    VARCHAR(36),
    opened_at       TIMESTAMP NOT NULL,
    closed_at       TIMESTAMP,
    hold_duration_min INTEGER,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_th_user_id ON trade_history(user_id);
CREATE INDEX idx_th_trader_id ON trade_history(trader_id);
CREATE INDEX idx_th_closed_at ON trade_history(closed_at);
CREATE INDEX idx_th_pair ON trade_history(pair);
```

### 3-3. ログテーブル

**pipeline_logs（パイプライン実行ログ - 設計思想: 透明性）**
```sql
CREATE TABLE pipeline_logs (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    execution_id    VARCHAR(36) NOT NULL,
    trader_id       INTEGER NOT NULL REFERENCES traders(id),
    pair            VARCHAR(20) NOT NULL,
    timestamp       TIMESTAMP NOT NULL,     -- 評価時刻（UTC）
    stage           VARCHAR(10) NOT NULL,   -- m1/m2/m3/m4/guard
    mode            VARCHAR(10),            -- rule/aiAssist/aiFull
    input_snapshot  JSONB NOT NULL,
    output_snapshot JSONB NOT NULL,         -- _debug含む
    config_snapshot JSONB NOT NULL,
    elapsed_ms      NUMERIC(10,2),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_pl_user_id ON pipeline_logs(user_id);
CREATE INDEX idx_pl_execution_id ON pipeline_logs(execution_id);
CREATE INDEX idx_pl_trader_id_timestamp ON pipeline_logs(trader_id, timestamp);
CREATE INDEX idx_pl_stage ON pipeline_logs(stage);
```

**safeguard_logs（セーフガード発動履歴）**
```sql
CREATE TABLE safeguard_logs (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    trader_id       INTEGER NOT NULL REFERENCES traders(id),
    pair            VARCHAR(20),
    timestamp       TIMESTAMP NOT NULL,
    trigger_type    VARCHAR(20) NOT NULL,  -- tick/bar_closed/trade_closed/pre_entry/timer
    guard_id        VARCHAR(10) NOT NULL,  -- SG-001 等
    result          VARCHAR(10) NOT NULL,  -- pass/warn/block/halt
    reason          VARCHAR(200),
    details_json    JSONB,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_sgl_user_id ON safeguard_logs(user_id);
CREATE INDEX idx_sgl_trader_id_timestamp ON safeguard_logs(trader_id, timestamp);
CREATE INDEX idx_sgl_result ON safeguard_logs(result);
```

**ai_decision_logs（AI判断履歴）**
```sql
CREATE TABLE ai_decision_logs (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    trader_id       INTEGER NOT NULL REFERENCES traders(id),
    execution_id    VARCHAR(36),
    stage           VARCHAR(10) NOT NULL,
    timestamp       TIMESTAMP NOT NULL,
    provider        VARCHAR(20) NOT NULL,
    model           VARCHAR(50) NOT NULL,
    system_prompt_hash VARCHAR(64),
    user_prompt     TEXT,
    raw_response    TEXT,
    parsed_result   JSONB,
    parse_success   BOOLEAN NOT NULL,
    tokens_input    INTEGER,
    tokens_output   INTEGER,
    latency_ms      NUMERIC(10,2),
    adopted         BOOLEAN NOT NULL DEFAULT false,
    fallback_reason VARCHAR(100),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_adl_user_id ON ai_decision_logs(user_id);
CREATE INDEX idx_adl_trader_id ON ai_decision_logs(trader_id);
CREATE INDEX idx_adl_timestamp ON ai_decision_logs(timestamp);
```

**config_changes（パラメータ変更履歴 - 設計思想: チューニング支援）**
```sql
CREATE TABLE config_changes (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    trader_id       INTEGER NOT NULL REFERENCES traders(id),
    config_type     VARCHAR(20) NOT NULL,  -- model_stage/safeguard/trader
    stage           VARCHAR(10),           -- m1/m2/m3/m4/mx/null
    config_before   JSONB NOT NULL,
    config_after    JSONB NOT NULL,
    changed_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    changed_by      INTEGER NOT NULL REFERENCES users(id),
    change_reason   TEXT
);
CREATE INDEX idx_cc_user_id ON config_changes(user_id);
CREATE INDEX idx_cc_trader_id ON config_changes(trader_id);
CREATE INDEX idx_cc_changed_at ON config_changes(changed_at);
```

### 3-4. 設定テーブル

**exchange_configs（取引所APIキー）**
```sql
CREATE TABLE exchange_configs (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    exchange_type   VARCHAR(20) NOT NULL,  -- gmo_fx / bitbank
    api_key_encrypted BYTEA NOT NULL,      -- 暗号化済みAPIキー
    api_secret_encrypted BYTEA NOT NULL,   -- 暗号化済みシークレット
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, exchange_type)
);
-- マスターキーはDB外で管理【監査3】
```

**ai_model_configs（AI APIキー+モデル設定）**
```sql
CREATE TABLE ai_model_configs (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    provider        VARCHAR(20) NOT NULL,  -- openai / gemini / claude
    api_key_encrypted BYTEA NOT NULL,
    default_model   VARCHAR(50),
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, provider)
);
```

**system_default_prompts（4段階デフォルトプロンプト）**
```sql
CREATE TABLE system_default_prompts (
    id              SERIAL PRIMARY KEY,
    stage           VARCHAR(10) NOT NULL UNIQUE,  -- m1/m2/m3/m4
    system_prompt   TEXT NOT NULL,
    version         INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**notification_emails（通知先メールアドレス）**
```sql
CREATE TABLE notification_emails (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    email           VARCHAR(255) NOT NULL,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_ne_user_id ON notification_emails(user_id);
```

**daily_notification_configs（デイリー通知設定）**
```sql
CREATE TABLE daily_notification_configs (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    enabled         BOOLEAN DEFAULT false,
    send_time_utc   TIME DEFAULT '22:00',    -- UTC（JST 07:00相当）
    include_pnl     BOOLEAN DEFAULT true,
    include_trades  BOOLEAN DEFAULT true,
    include_guards  BOOLEAN DEFAULT true,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(user_id)
);
```

### 3-5. UI永続化テーブル

**market_watch_configs（マーケットウォッチ設定）**
```sql
CREATE TABLE market_watch_configs (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    pair            VARCHAR(20) NOT NULL,
    display_order   INTEGER NOT NULL DEFAULT 0,
    is_visible      BOOLEAN DEFAULT true,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_mwc_user_id ON market_watch_configs(user_id);
```

**chart_configs（チャートパネル設定）**
```sql
CREATE TABLE chart_configs (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    pair            VARCHAR(20) NOT NULL,
    timeframe       VARCHAR(10) NOT NULL DEFAULT 'H1',
    indicators      JSONB DEFAULT '[]',      -- 表示中のインジケーター
    chart_type      VARCHAR(20) DEFAULT 'candlestick',
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, pair)
);
```

### 3-6. バックテスト・データテーブル

**historical_ohlcv（ヒストリカルOHLCVデータ）**
```sql
CREATE TABLE historical_ohlcv (
    id              SERIAL PRIMARY KEY,
    pair            VARCHAR(20) NOT NULL,
    timeframe       VARCHAR(10) NOT NULL,
    timestamp       TIMESTAMP NOT NULL,
    open            NUMERIC(20,8) NOT NULL,
    high            NUMERIC(20,8) NOT NULL,
    low             NUMERIC(20,8) NOT NULL,
    close           NUMERIC(20,8) NOT NULL,
    volume          NUMERIC(20,8) NOT NULL DEFAULT 0,
    source          VARCHAR(20),             -- gmo/bitbank/histdata/dukascopy
    UNIQUE(pair, timeframe, timestamp)
);
CREATE INDEX idx_ho_pair_tf_ts ON historical_ohlcv(pair, timeframe, timestamp);
```

**backtest_runs（バックテスト実行記録）**
```sql
CREATE TABLE backtest_runs (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    trader_id       INTEGER NOT NULL REFERENCES traders(id),
    status          VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending/running/completed/failed
    config_snapshot JSONB NOT NULL,          -- 実行時のパラメータ
    pair            VARCHAR(20) NOT NULL,
    timeframe       VARCHAR(10) NOT NULL,
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    -- 結果サマリ
    total_trades    INTEGER,
    win_rate        NUMERIC(5,2),
    profit_factor   NUMERIC(8,2),
    max_drawdown_pct NUMERIC(5,2),
    sharpe_ratio    NUMERIC(8,4),
    total_pnl       NUMERIC(15,2),
    avg_rr_ratio    NUMERIC(5,2),
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    error_message   TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_br_user_id ON backtest_runs(user_id);
```

**backtest_trades（バックテストシミュレート取引）**
```sql
CREATE TABLE backtest_trades (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    backtest_run_id INTEGER NOT NULL REFERENCES backtest_runs(id),
    pair            VARCHAR(20) NOT NULL,
    side            VARCHAR(4) NOT NULL,
    amount          NUMERIC(15,8),
    entry_price     NUMERIC(20,8),
    exit_price      NUMERIC(20,8),
    realized_pnl    NUMERIC(15,2),
    realized_pnl_pips NUMERIC(10,2),
    rr_ratio        NUMERIC(5,2),
    exit_reason     VARCHAR(50),
    entry_timestamp TIMESTAMP,
    exit_timestamp  TIMESTAMP,
    pipeline_log_json JSONB,         -- パイプラインログ（簡易版）
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_bt_backtest_run_id ON backtest_trades(backtest_run_id);
```

**simulation_history（ペーパートレード履歴）【監査2】**
```sql
CREATE TABLE simulation_history (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    trader_id       INTEGER NOT NULL REFERENCES traders(id),
    pair            VARCHAR(20) NOT NULL,
    side            VARCHAR(4) NOT NULL,
    amount          NUMERIC(15,8),
    entry_price     NUMERIC(20,8),
    exit_price      NUMERIC(20,8),
    realized_pnl    NUMERIC(15,2),
    exit_reason     VARCHAR(50),
    execution_id    VARCHAR(36),
    opened_at       TIMESTAMP,
    closed_at       TIMESTAMP,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_sh_user_id ON simulation_history(user_id);
-- 本番 trade_history とは物理的に別テーブル
```

### 3-7. 経済指標テーブル

**economic_events（経済指標カレンダー）**
```sql
CREATE TABLE economic_events (
    id              SERIAL PRIMARY KEY,
    event_name      VARCHAR(200) NOT NULL,
    currency        VARCHAR(3) NOT NULL,       -- USD, JPY, EUR, etc.
    importance      INTEGER NOT NULL,          -- 1-3（星）
    event_datetime  TIMESTAMP NOT NULL,        -- UTC
    actual_value    VARCHAR(50),
    forecast_value  VARCHAR(50),
    previous_value  VARCHAR(50),
    source          VARCHAR(50),
    fetched_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_ee_datetime ON economic_events(event_datetime);
CREATE INDEX idx_ee_currency ON economic_events(currency);
```

---

## 4. DB隔離設計【監査2】

```
TRADING_MODE=live:
  → positions, trade_history に書込み

TRADING_MODE=simulation:
  → simulation_history に書込み
  → positions テーブルは使用しない（MockExchangeのメモリ内で管理）

TRADING_MODE=backtest:
  → backtest_trades に書込み
  → historical_ohlcv から読取のみ
  → 本番テーブルには一切触れない
```

---

## 5. データ保持ポリシー

```
テーブル                    保持期間
---------------------------------------------
trade_history               永久
positions                   アクティブ中のみ
pipeline_logs               180日
safeguard_logs (BLOCK/HALT) 永久
safeguard_logs (WARN)       90日
ai_decision_logs            90日（adopted=true は永久）
config_changes              永久
historical_ohlcv            永久
backtest_runs/trades        永久
economic_events             365日
```

---

## 6. 関連設計書

- `03_safeguard_engine.md` - safeguard_configs, safeguard_logs
- `04_decision_pipeline.md` - pipeline_logs, config_changes, model_stage_configs
- `05_ai_integration.md` - ai_decision_logs, system_default_prompts
- `06_exchange_abstraction.md` - exchange_configs, positions, trade_history
- `08_api_specification.md` - 全テーブルに対応するCRUDエンドポイント
- `11_security.md` - exchange_configs/ai_model_configsの暗号化
