# 08. API仕様書

## 1. 概要

REST API + WebSocket の全エンドポイントを定義する。

**技術スタック:**
- フレームワーク: FastAPI
- 認証: JWT Bearer Token
- APIスキーマ: OpenAPI 3.0（自動生成）
- 命名規則: lowerCamelCase（Excel仕様準拠）

**【監査1】全エンドポイントのオーナーシップ検証:**
- `trader_id` を受け取る全APIに `@verify_ownership` デコレータを適用
- 不正アクセスは 403 Forbidden

---

## 2. 共通仕様

### 2-1. 認証

```
全Private APIにJWT Bearer Tokenが必要:
  Authorization: Bearer <jwt_token>

トークン取得: POST /api/v1/auth/login
トークン更新: POST /api/v1/auth/refresh
```

### 2-2. @verify_ownership デコレータ

```python
def verify_ownership(func):
    """trader_idがリクエストuser_idに属するか検証"""
    async def wrapper(request, trader_id: int, ...):
        user_id = get_current_user_id(request)
        trader = await get_trader(trader_id)
        if trader is None or trader.user_id != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        return await func(request, trader_id, ...)
    return wrapper
```

### 2-3. レスポンス形式

```json
成功:
{
  "status": "ok",
  "data": { ... }
}

エラー:
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "..."
  }
}
```

### 2-4. ページネーション

```
クエリパラメータ:
  page: int (default 1)
  perPage: int (default 20, max 100)

レスポンス:
{
  "data": [...],
  "pagination": {
    "page": 1,
    "perPage": 20,
    "totalItems": 150,
    "totalPages": 8
  }
}
```

---

## 3. エンドポイント一覧

### 3-1. 認証（Auth）

```
POST   /api/v1/auth/login           ログイン
POST   /api/v1/auth/refresh         トークン更新
POST   /api/v1/auth/logout          ログアウト
```

**POST /api/v1/auth/login**
```
Request:
  { "email": "user@example.com", "password": "..." }
Response:
  { "accessToken": "...", "refreshToken": "...", "expiresIn": 3600 }
```

### 3-2. アカウント（Account）

```
GET    /api/v1/account              アカウント情報取得
PUT    /api/v1/account              アカウント情報更新
```

### 3-3. ダッシュボード（Dashboard）

```
GET    /api/v1/dashboard/summary                  サマリ取得
POST   /api/v1/dashboard/close-all                全ポジション決済
POST   /api/v1/dashboard/stop-all                 全トレーダー停止
POST   /api/v1/dashboard/start-all                全トレーダー開始
```

**GET /api/v1/dashboard/summary**
```
Response:
{
  "totalPnlToday": 15000,
  "totalPnlMonth": 85000,
  "activeTraders": 3,
  "openPositions": 5,
  "traders": [
    {
      "traderId": 1,
      "traderName": "短期トレーダーA",
      "status": "running",
      "pnlToday": 5000,
      "openPositions": 2,
      "pipelineState": {
        "lastM1": { "trend": "UP", "timestamp": "..." },
        "lastM2": { "setupValid": true, "timestamp": "..." },
        "guardState": { "entryAllowed": true, "blockingGuards": [] }
      }
    }
  ]
}
```

### 3-4. トレーダー（Traders）

```
GET    /api/v1/traders                            一覧取得
POST   /api/v1/traders                            新規作成
GET    /api/v1/traders/{traderId}                  詳細取得
PUT    /api/v1/traders/{traderId}                  更新
DELETE /api/v1/traders/{traderId}                  削除
POST   /api/v1/traders/{traderId}/start            開始
POST   /api/v1/traders/{traderId}/stop             停止
POST   /api/v1/traders/{traderId}/close-all        全ポジション決済
```

**POST /api/v1/traders**
```
Request:
{
  "traderName": "短期トレーダーA",
  "tradeType": "FX",
  "symbols": ["USD_JPY"],
  "capitalJpy": 1000000,
  "orderUnitLots": 1,
  "strategyText": "短期トレンドフォロー...",
  "notifyEmail": "user@example.com",
  "notifyOnEntry": true,
  "notifyOnStop": true,
  "notifyOnError": true,
  "notifyOnExit": true,
  "notifyOnTarget": true
}
```

### 3-5. モデルステージ設定（Model Stages）

```
GET    /api/v1/traders/{traderId}/model-stages              全段階の設定取得
GET    /api/v1/traders/{traderId}/model-stages/{stage}      指定段階の設定取得
PUT    /api/v1/traders/{traderId}/model-stages/{stage}      指定段階の設定更新
```

**PUT /api/v1/traders/{traderId}/model-stages/m1**
```
Request:
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
Response:
{
  "status": "ok",
  "data": { ... },
  "configChange": {
    "id": 42,
    "changedAt": "2026-02-22T10:00:00Z"
  }
}
```

### 3-6. セーフガード設定（Safeguards）

```
GET    /api/v1/traders/{traderId}/safeguards         設定取得
PUT    /api/v1/traders/{traderId}/safeguards         設定更新
GET    /api/v1/traders/{traderId}/safeguards/logs    発動履歴
```

**PUT /api/v1/traders/{traderId}/safeguards**
```
Request:
{
  "maxDailyLossPct": 10,
  "maxMonthlyLossPct": 20,
  "maxDrawdownPct": 30,
  "stopOnProfit": { "enabled": false, "targetPct": 10 },
  "consecutiveLoss": { "enabled": true, "max": 3, "cooldownMin": 60, "halveLot": false },
  "spread": { "showAvg": true, "showCurrent": true, "maxMultiple": 2 },
  "atrSpike": { "enabled": true, "lookbackBars": 20, "maxMultiple": 1.8 },
  "rangeSpike": { "enabled": true, "windowMin": 5, "maxPips": 50 },
  "session": { ... },
  "econStop": { ... },
  "regime": { ... },
  "exec": { ... },
  "aiFailsafe": { ... }
}
```

### 3-7. マーケットウォッチ（Market Watch）

```
GET    /api/v1/market-watch                         一覧取得
POST   /api/v1/market-watch                         ペア追加
DELETE /api/v1/market-watch/{id}                     ペア削除
PUT    /api/v1/market-watch/reorder                  並び替え
```

### 3-8. チャート（Charts）

```
GET    /api/v1/charts/ohlcv                          OHLCV取得
GET    /api/v1/charts/indicators                     指標データ取得
GET    /api/v1/charts/markers                        マーカー（売買サイン）取得
GET    /api/v1/charts/config                         チャート設定取得
PUT    /api/v1/charts/config                         チャート設定更新
```

**GET /api/v1/charts/ohlcv**
```
Query:
  pair=USD_JPY
  timeframe=H1
  limit=200
Response:
{
  "data": [
    { "t": "2026-02-22T10:00:00Z", "o": 149.50, "h": 149.80, "l": 149.30, "c": 149.65, "v": 1200 }
  ]
}
```

### 3-9. 通知設定（Notifications）

```
GET    /api/v1/notifications/smtp                    SMTP設定取得
PUT    /api/v1/notifications/smtp                    SMTP設定更新
GET    /api/v1/notifications/emails                  メールアドレス一覧
POST   /api/v1/notifications/emails                  メールアドレス追加
DELETE /api/v1/notifications/emails/{id}              メールアドレス削除
POST   /api/v1/notifications/test                    テスト送信
GET    /api/v1/notifications/daily                   デイリー通知設定取得
PUT    /api/v1/notifications/daily                   デイリー通知設定更新
```

### 3-10. 取引履歴（History）

```
GET    /api/v1/history                               一覧取得（ページネーション）
GET    /api/v1/history/{tradeId}                     詳細取得（4段階判定含む）
GET    /api/v1/history/chart-data                    チャート用損益データ
GET    /api/v1/history/export/csv                    CSV出力
```

**GET /api/v1/history**
```
Query:
  traderId=1 (optional)
  pair=USD_JPY (optional)
  dateFrom=2026-01-01 (optional)
  dateTo=2026-02-22 (optional)
  page=1
  perPage=20
```

**GET /api/v1/history/{tradeId}**
```
Response:
{
  "trade": { ... },
  "pipelineLogs": [
    { "stage": "m1", "output": {...}, "config": {...}, "elapsedMs": 2.5 },
    { "stage": "m2", "output": {...}, "config": {...}, "elapsedMs": 1.8 },
    { "stage": "m3", "output": {...}, "config": {...}, "elapsedMs": 3.2 }
  ],
  "safeguardLogs": [
    { "guardId": "SG-012", "result": "pass", "details": {...} }
  ]
}
```

### 3-11. バックテスト（Backtest）

```
POST   /api/v1/backtests                             バックテスト実行開始
GET    /api/v1/backtests                             一覧取得
GET    /api/v1/backtests/{backtestId}                結果取得
GET    /api/v1/backtests/{backtestId}/trades          取引一覧
DELETE /api/v1/backtests/{backtestId}                結果削除
```

**POST /api/v1/backtests**
```
Request:
{
  "traderId": 1,
  "pair": "USD_JPY",
  "timeframe": "M5",
  "startDate": "2025-01-01",
  "endDate": "2025-12-31",
  "useCurrentConfig": true
}
Response:
{
  "backtestId": 42,
  "status": "pending"
}
```

### 3-12. パイプラインログ（Pipeline Logs）

```
GET    /api/v1/pipeline-logs                         ログ照会
GET    /api/v1/pipeline-logs/{executionId}            実行単位のログ詳細
```

**GET /api/v1/pipeline-logs**
```
Query:
  traderId=1
  pair=USD_JPY (optional)
  stage=m1 (optional)
  dateFrom=2026-02-22 (optional)
  dateTo=2026-02-22 (optional)
  page=1
  perPage=20
```

### 3-13. 設定変更履歴（Config Changes）

```
GET    /api/v1/config-changes                        変更履歴一覧
GET    /api/v1/config-changes/{changeId}             変更詳細（before/after diff）
```

### 3-14. システム設定（Settings）

```
GET    /api/v1/settings/exchanges                    取引所API設定取得
PUT    /api/v1/settings/exchanges/{exchangeType}     取引所API設定更新
GET    /api/v1/settings/ai                           AI API設定取得
PUT    /api/v1/settings/ai/{provider}                AI API設定更新
GET    /api/v1/settings/system-status                システム状態取得
```

---

## 4. WebSocket エンドポイント

### 4-1. 接続

```
URL: ws://host/api/v1/ws
認証: クエリパラメータでトークン送信
  ws://host/api/v1/ws?token=<jwt_token>
```

### 4-2. チャンネル

**prices（リアルタイム価格）**
```
Subscribe:
  { "action": "subscribe", "channel": "prices", "pairs": ["USD_JPY", "EUR_JPY"] }

Message:
  { "channel": "prices", "pair": "USD_JPY", "bid": 149.50, "ask": 149.52,
    "timestamp": "2026-02-22T10:00:00.123Z" }
```

**trader_updates（トレーダー状態更新）**
```
Subscribe:
  { "action": "subscribe", "channel": "trader_updates", "traderIds": [1, 2] }

Message:
  { "channel": "trader_updates", "traderId": 1,
    "type": "position_opened",
    "data": { "pair": "USD_JPY", "side": "BUY", "amount": 1.0, "price": 149.50 } }
```

**alerts（アラート通知）**
```
Subscribe:
  { "action": "subscribe", "channel": "alerts" }

Message:
  { "channel": "alerts", "type": "safeguard_triggered",
    "data": { "traderId": 1, "guardId": "SG-001", "result": "halt",
              "reason": "Daily loss limit reached" } }
```

**pipeline_status（パイプライン状態）**
```
Subscribe:
  { "action": "subscribe", "channel": "pipeline_status", "traderIds": [1] }

Message:
  { "channel": "pipeline_status", "traderId": 1,
    "executionId": "...", "stage": "m2", "result": "setupValid=true",
    "timestamp": "..." }
```

---

## 5. エラーコード一覧

```
コード                        HTTP   説明
-------------------------------------------------------------
VALIDATION_ERROR              400    入力バリデーションエラー
UNAUTHORIZED                  401    認証失敗
FORBIDDEN                     403    権限なし（テナント隔離違反含む）
NOT_FOUND                     404    リソース未発見
TRADER_NOT_ACTIVE             409    トレーダーが非アクティブ
TRADER_HALTED                 409    トレーダーが停止中
EXCHANGE_ERROR                502    取引所APIエラー
AI_PROVIDER_ERROR             502    AIプロバイダエラー
RATE_LIMIT_EXCEEDED           429    レートリミット超過
INTERNAL_ERROR                500    内部エラー
```

---

## 6. 関連設計書

- `07_データベーススキーマ.md` - 全テーブル定義
- `10_フロントエンドアーキテクチャ.md` - フロントエンドからの呼出し
- `11_セキュリティ.md` - 認証・認可の詳細
