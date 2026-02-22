# 14. コスト管理設計書

## 1. 概要【監査4】

LLM API呼出しのレートリミットとコスト予算管理を定義する。
ruleモードではAIコストゼロだが、aiAssist/aiFullモード使用時のコスト爆発を防止する。

---

## 2. レートリミット

### 2-1. トレーダー単位

```
デフォルト制限:
  - 1分間のAI呼出し上限: 10回/分/トレーダー
  - 上限到達時: 次のトリガーまで待機（注文は出さない）
```

### 2-2. システム全体

```
デフォルト制限:
  - 全トレーダー合計の1分間上限: 30回/分
  - 上限到達時: 優先度の低いトレーダーから順にスキップ
```

### 2-3. 実装

```python
class AIRateLimiter:
    """AI呼出しレートリミッター"""

    def __init__(
        self,
        per_trader_per_minute: int = 10,
        global_per_minute: int = 30,
    ):
        self.per_trader_limit = per_trader_per_minute
        self.global_limit = global_per_minute
        self.trader_calls: dict[int, list[datetime]] = {}
        self.global_calls: list[datetime] = []

    def can_call(self, trader_id: int) -> bool:
        """呼出し可能か判定"""
        now = datetime.utcnow()
        one_min_ago = now - timedelta(minutes=1)

        # グローバルチェック
        self.global_calls = [t for t in self.global_calls if t > one_min_ago]
        if len(self.global_calls) >= self.global_limit:
            return False

        # トレーダーチェック
        calls = self.trader_calls.get(trader_id, [])
        calls = [t for t in calls if t > one_min_ago]
        self.trader_calls[trader_id] = calls
        if len(calls) >= self.per_trader_limit:
            return False

        return True

    def record_call(self, trader_id: int) -> None:
        """呼出しを記録"""
        now = datetime.utcnow()
        self.global_calls.append(now)
        self.trader_calls.setdefault(trader_id, []).append(now)
```

---

## 3. トークン予算管理

### 3-1. 日次予算

```
デフォルト: 1,000,000トークン/日（入力+出力合計）
超過時: 全トレーダーのAI呼出しを停止（ruleモードにフォールバック）
        + メール通知
```

### 3-2. 月次コスト予算

```
設定可能（デフォルト: 無制限）
超過時: 全トレーダーの自動取引を停止 + メール通知
```

### 3-3. 警告閾値

```
日次予算残量80%到達時: 警告メール
月次予算残量80%到達時: 警告メール
```

### 3-4. コスト記録

```python
@dataclass
class AIUsageRecord:
    """AI使用量レコード"""
    trader_id: int
    stage: str                # m1/m2/m3/m4
    provider: str             # openai/gemini/claude
    model: str
    tokens_input: int
    tokens_output: int
    estimated_cost_usd: float
    timestamp: datetime

class BudgetTracker:
    """コスト予算トラッカー"""

    async def record_usage(self, record: AIUsageRecord) -> None:
        """使用量を記録"""
        ...

    async def get_daily_usage(self, date: date) -> DailyUsageSummary:
        """日次使用量サマリ取得"""
        ...

    async def check_budget(self) -> BudgetStatus:
        """予算状態チェック"""
        ...
```

---

## 4. ruleモード活用によるコスト最適化

```
コスト戦略:
  1. ruleモードをデフォルト推奨（AI APIコストゼロ）
  2. aiAssistモードでもAI呼出しは「最終確認」のみ（トークン消費抑制）
  3. バックテスト時はMockAIProvider（API呼出回避）
  4. AI呼出しはイベント駆動（毎分呼ばない）

コスト見積もり（aiAssistモード、1トレーダー、GPT-4o）:
  M1: 24回/日 × $0.01 = $0.24/日
  M2: 96回/日 × $0.01 = $0.96/日
  M3: 48回/日 × $0.01 = $0.48/日
  M4: 100回/日 × $0.01 = $1.00/日
  合計: 約$2.68/日 ≈ ¥400/日
```

---

## 5. 関連設計書

- `05_ai_integration.md` - AI呼出条件、フェイルセーフ
- `07_database_schema.md` - AIコスト記録テーブル（ai_decision_logsで兼用）
