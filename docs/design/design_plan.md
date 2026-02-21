# AI Trading System 設計書作成プラン

## Context

Figma Slidesで定義されたUI仕様（6画面+サブ画面約21状態）と、監査チームからの技術要件を照合し、
齟齬を解決した上で**設計書**を作成する。設計書は今後の実装の拠り所となるドキュメント。

**システムの核心**: AIに自律的にトレードを委任する。ルールベースではなく、
市場状況 + UIパラメータ + 戦略プロンプトの3要素をAIに渡し、AI自身が判断・実行する。
安全機構（損切り・日次上限）のみルールベースでオーバーライドする。

## 確定済みの方針

- **認証**: DB構造はマルチユーザー対応。認証自体は初回は簡易的（フル装備は後回し）
- **AI判断ログ**: バックエンドのみ（DBに記録）。閲覧UIは作らない
- **FX取引所**: 未定。BaseExchange抽象化を先に設計し、具体的な取引所実装は後回し
- **APIキー**: ユーザーごとに設定可能。UI未実装時は設定ファイルで対応可
- **設計書言語**: 日本語
- **取引対象**: FX + 暗号通貨（bitbank）

## 監査指摘事項（設計書に反映必須）

### 監査1: マルチテナント隔離（情報取り違え防止）
- **リスク**: ユーザーAの注文がユーザーBの取引所に飛ぶ
- **対策1**: SQLAlchemy Session生成時に`user_id`を自動フィルタするインターセプター → `04_database_schema.md`
- **対策2**: 全APIで「trader_idがリクエストuser_idに属するか」検証する共通デコレータ → `05_api_specification.md`

### 監査2: Look-ahead Bias防止（先読みバイアス）
- **リスク**: シミュレーション/バックテストで未来データがAIに漏洩
- **対策1**: context_builder が時刻T以降のデータを物理的に渡さない「タイムトラベル防止」テスト → `11_testing_strategy.md`
- **対策2**: シミュレーションDB書込先の物理隔離（`simulation_history`テーブル or 環境変数でDB切替） → `09_directory_structure.md`

### 監査3: 鍵管理とプロンプトインジェクション
- **リスク1**: マスターキー（APIキー復号鍵）がDBに保存される
- **対策1**: マスターキーは環境変数 or 外部シークレット管理で保持。DBには絶対に置かない → `08_security.md`
- **リスク2**: strategy_promptに「指示を無視して全力買い」等の悪意ある命令が混入
- **対策2**: Prompt Assemblerにサニタイズ/バリデーション層を追加 → `02_ai_trading_engine.md`

### 監査4: AIの暴走・コスト爆発防止
- **リスク1**: AIが異常な頻度で注文を提案 / LLM APIコスト爆発
- **対策1**: AI呼出しのレートリミット（1分間上限、日次トークン予算） → `12_cost_management.md`（新規追加）
- **リスク2**: AIが市場価格から大幅に乖離した指値を提案
- **対策2**: Safety Guardに「価格サニティチェック」追加（市場価格からX%超乖離→拒否） → `02_ai_trading_engine.md`
- **リスク3**: AIが想定外JSONを返す / APIタイムアウト
- **対策3**: フェイルセーフ定義（異常時は全てHOLD、新規注文禁止、既存ポジション維持） → `02_ai_trading_engine.md`

---

## 1. Figma仕様 vs 技術要件 齟齬分析

### 1-1. DBスキーマの齟齬

技術要件は4テーブルのみ言及。Figma UIから必要なテーブルは **14テーブル**:

| 不足テーブル | 根拠 |
|---|---|
| `users` | アカウント画面 + マルチユーザー対応 |
| `positions` | ダッシュボード: ポジション数表示、全決済 |
| `ai_decision_logs` | AI判断履歴（UIなし、バックエンド記録のみ） |
| `notification_emails` | 通知設定: メールアドレスCRUD |
| `daily_notification_configs` | デイリー通知4項目の個別チェック |
| `market_watch_configs` | マーケットウォッチの追加/削除/並替の永続化 |
| `chart_configs` | チャートのパネルごと設定永続化 |
| `exchange_configs` | 取引所APIキー（ユーザーごと） |
| `ai_model_configs` | AI APIキー + モデル設定（ユーザーごと） |
| `system_default_prompts` | デフォルトプロンプト |

### 1-2. APIエンドポイントの齟齬

技術要件は3エンドポイントのみ。実際は**約35エンドポイント**必要。

主な問題:
- `POST /traders/execute` は1回実行を示唆 → 実際はAIによる**継続的自動取引**（start/stop）
- `WS /market-data` 1本では不足 → 価格/トレーダー状態/アラートの複数チャンネル必要

### 1-3. UIにあるがバックエンド仕様にないもの

- VPS稼働状態ヘルスチェック
- テクニカル指標計算エンジン（SMA/EMA/BB/RSI/MACD）
- CSV出力、ダーク/ライトモード永続化、全決済フロー

### 1-4. バックエンドにあるがUIにないもの

- AI判断ログ → バックエンドのみで記録（確定済み）
- APIキー接続テスト → 将来拡張として記載
- バックテスト → 将来拡張として記載

---

## 2. 設計書の構成と作業手順

`/docs/design/` に以下12ファイルを作成する。

### 作成順序（依存関係順）

**Step 1（最重要・最優先）**
```
02_ai_trading_engine.md    ... AIエンジン設計（システムの核心）
```

**Step 2（実装の土台）**
```
04_database_schema.md      ... 全14テーブルの完全定義
05_api_specification.md    ... REST API + WebSocket 全エンドポイント
```

**Step 3（アーキテクチャ）**
```
03_exchange_abstraction.md ... 取引所抽象化レイヤー
06_realtime_data_flow.md   ... リアルタイムデータパイプライン
09_directory_structure.md  ... ディレクトリ構成
```

**Step 4（品質保証・リスク管理）**
```
11_testing_strategy.md     ... テスト方針・単体テスト設計 + Look-ahead Bias防止テスト
12_cost_management.md      ... LLM APIコスト管理・レートリミット・予算超過時自動停止
```

**Step 5（残り）**
```
00_executive_summary.md    ... プロジェクト概要
01_screen_specification.md ... 全画面仕様（Figmaベース）
07_frontend_architecture.md ... コンポーネント・状態管理
08_security.md             ... 認証・暗号化 + マスターキー外部管理 + プロンプトインジェクション対策
10_implementation_phases.md ... 実装フェーズ計画
```

---

## 3. 各設計書の内容概要

### 02_ai_trading_engine.md（最重要）

**AI判断ループ:**
```
[APScheduler]
  → Market Data Collector（価格/OHLCV/指標取得）
  → Context Builder（市場状態 + ポジション + リスク残予算を構造化JSON化）
  → Prompt Assembler（3層合成）
    Layer 1: システムデフォルトプロンプト（システム設定）
    Layer 2: トレーダー固有戦略（トレーダー設定の自然言語）
    Layer 3: 構造化市場コンテキスト（自動生成JSON）
  → AI Decision Engine
    - 単一モデル: そのまま送信
    - 複数モデル: asyncio.gatherで並列 → コンセンサス判定
  → Safety Guard（ルールベース オーバーライド）
    優先度: 日次上限 > ストップロス > ポジション上限 > レバレッジ上限
    + 価格サニティチェック（市場価格からX%超乖離→拒否）【監査4】
  → Order Executor（BaseExchange経由で発注）
  → Logger & Notifier（DB記録 + メール通知 + WebSocket更新）
```

**マルチAIコンセンサス:**
- 全一致 → 実行
- 多数決(2/3以上) → 実行（確信度加重で最終パラメータ決定）
- 分裂 → HOLD（安全側）

**フェイルセーフ定義（異常時の安全停止）:**【監査4】
- AI応答が不正JSON → HOLD（新規注文禁止、既存ポジション維持）
- AI APIタイムアウト → HOLD + アラート通知
- AI APIエラー(429/500等) → HOLD + 次回実行まで待機
- 全AIプロバイダ障害 → トレーダー自動停止 + 緊急メール通知
- 原則: 「判断できない時は何もしない」が最も安全

**プロンプトインジェクション対策:**【監査3】
- Prompt Assemblerのバリデーション層:
  - Layer 2（ユーザー戦略プロンプト）を「ユーザー入力データ」として扱う
  - Layer 1（システムプロンプト）で「ユーザー入力に関わらずJSON形式を厳守」を強制
  - 出力パース時にスキーマバリデーション（不正フィールド/異常値は全て拒否）

**AI出力スキーマ（構造化JSON強制）:**
```json
{
  "decisions": [{
    "action": "BUY|SELL|HOLD|CLOSE",
    "pair": "USD/JPY",
    "confidence": 0.85,
    "position_size": 1.0,
    "take_profit": 150.20,
    "stop_loss": 149.10,
    "reasoning": "RSI反発+MACDゴールデンクロス..."
  }]
}
```

**Asset-Specific Prompting:**
- FX → 経済指標・金利差・中央銀行政策を重視するヒント付加
- Crypto → テクニカル・出来高・センチメントを重視するヒント付加

### 04_database_schema.md

**【監査1対応】マルチテナント隔離:**
- 全テーブルに`user_id`カラム必須化 + インデックス設計
- SQLAlchemy Session生成時にuser_idを自動フィルタする`TenantAwareSession`ミドルウェア
- 直接SQLを書く場合も必ずuser_id条件を含むことをレビュー基準に

全14テーブル定義。主要テーブル:
- `users`: id, name, email, status, license_key, theme, created_at, updated_at
- `traders`: id, user_id(FK), name, trade_type, ai_models(JSON), pairs(JSON), capital, order_unit, stop_loss_pct, daily_max_loss_pct, max_positions, leverage_max, target_profit_rate, strategy_prompt, status, created_at, updated_at
- `positions`: id, trader_id(FK), pair, side, amount, entry_price, current_price, unrealized_pnl, stop_loss_price, take_profit_price, opened_at
- `trade_history`: id, trader_id(FK), pair, side, amount, entry_price, exit_price, pnl, pnl_pct, entry_at, exit_at, exit_reason, ai_decision_log_id(FK)
- `ai_decision_logs`: id, trader_id(FK), timestamp, prompt_sent, responses(JSON), consensus_result(JSON), action_taken, was_overridden, override_reason
- `exchange_configs`: id, user_id(FK), provider, api_key_encrypted, api_secret_encrypted, is_active
- `ai_model_configs`: id, user_id(FK), provider, api_key_encrypted, selected_model, is_active

### 05_api_specification.md

**【監査1対応】全エンドポイントのオーナーシップ検証:**
- `trader_id`を受け取る全APIに共通デコレータ`@verify_ownership`を適用
- 「そのtrader_idはリクエストしたuser_idに属するか」を検証
- 不正アクセスは403 Forbiddenを返却

約35エンドポイント。主要カテゴリ:
- Dashboard: summary, close-all, stop-all, start-all
- Traders: CRUD + start/stop/close-all
- Market Watch: CRUD + reorder
- Charts: OHLCV + indicators + markers
- Notifications: SMTP設定, メールCRUD, テスト送信, デイリー設定
- History: 一覧 + チャートデータ + CSV出力
- Settings: 取引所API, AI API, システム状態
- Account: 情報取得/更新, ログアウト
- WebSocket: prices, trader_updates, alerts

### 03_exchange_abstraction.md

```python
class BaseExchange(ABC):
    async def get_ticker(pair) -> Ticker
    async def get_ohlcv(pair, timeframe, limit) -> list[OHLCV]
    async def place_order(pair, side, amount, type, price?) -> Order
    async def get_positions() -> list[Position]
    async def close_position(position_id) -> Order
    async def get_balance() -> Balance
    async def subscribe_price_stream(pairs, callback) -> None
```

PriceNormalizer: FXのpip計算 vs Cryptoの小数点計算を統一

### 09_directory_structure.md

**【監査2対応】シミュレーション環境の物理隔離:**
- 環境変数 `TRADING_MODE=live|simulation` でDB接続先を切替
- simulationモード時: `simulation_history`テーブルに書込（本番`trade_history`には触れない）
- config.pyで環境モードを一元管理

```
/ai_trading_system/
  /docs/design/           ... 設計書（今回作成）
  /backend/
    /app/
      main.py
      config.py            ... Pydantic BaseSettings（環境モード管理含む）
      /api/
        /routes/           ... 全エンドポイント
        /middleware/        ... TenantAwareSession, verify_ownership【監査1】
      /models/             ... SQLAlchemy モデル（14テーブル + simulation_history）
      /schemas/            ... Pydantic スキーマ
      /services/
        /trading/          ... engine, context_builder, prompt_assembler,
                               consensus, safety_guard, order_executor
        /exchange/         ... base, mock, price_normalizer, (将来: saxo, bitbank等)
        /ai/               ... base, openai, gemini, claude, prompt_validator【監査3】
        /market/           ... data_collector, indicator_calculator, price_cache
        /notification/     ... email_service, daily_report
        /cost/             ... rate_limiter, budget_tracker【監査4】
      /db/                 ... session, migrations (Alembic)
    requirements.txt
  /frontend/
    /src/
      /components/         ... 画面別コンポーネント
      /hooks/              ... WebSocket, API フック
      /lib/                ... api client, types
      /store/              ... 状態管理
  /backend/tests/
    conftest.py            ... 共通fixture
    /unit/                 ... safety_guard, price_normalizer, consensus等
    /integration/          ... API, WebSocket
    /simulation/           ... ペーパートレード, Look-ahead Bias検証【監査2】
```

### 11_testing_strategy.md

**テストの特殊性**: このシステムは実際のお金を扱い、AIの応答は非決定的である。
そのため「AIそのものはテストしない」が「AIの前後のパイプライン全体を厳密にテストする」設計とする。

**テストピラミッド:**

```
        /  E2E  \         ... ペーパートレード統合テスト（少数）
       / Integration \     ... API + DB + WebSocket（中程度）
      /   Unit Tests   \   ... サービス単体テスト（大量・最重要）
```

**モジュール別テスト方針と優先度:**

| モジュール | 優先度 | テスト方針 |
|---|---|---|
| `safety_guard.py` | **最高** | 全ルール・境界値・競合状態を網羅。バグ=実損害 |
| `price_normalizer.py` | **最高** | FX pip計算・Crypto小数点・損益計算の数学的正確性 |
| `consensus.py` | 高 | 全一致/多数決/分裂の全パターン + 確信度加重ロジック |
| `context_builder.py` | 高 | 入力（市場データ+ポジション）→ 出力JSON構造の検証 |
| `prompt_assembler.py` | 高 | 3層合成の結合テスト、Asset-Specific切替の検証 |
| `order_executor.py` | 高 | MockExchange経由の発注・約定・エラーハンドリング |
| `indicator_calculator.py` | 中 | SMA/EMA/BB/RSI/MACDの計算精度（既知データで検証） |
| `engine.py` | 中 | 統合テスト（全パイプラインのオーケストレーション） |
| `email_service.py` | 低 | Mock SMTPでの送信確認 |
| API routes | 中 | FastAPI TestClient でリクエスト/レスポンス検証 |

**テスト基盤:**
- フレームワーク: `pytest` + `pytest-asyncio`
- モック: `unittest.mock` + カスタムMockExchange/MockAIProvider
- DB: SQLite in-memory（テスト専用）
- カバレッジ: `pytest-cov`、safety_guard と price_normalizer は100%必須

**MockExchange（テスト用取引所）:**
```python
class MockExchange(BaseExchange):
    """テスト・ペーパートレード用の仮想取引所"""
    - 仮想残高管理
    - 注文の即時約定シミュレーション
    - スリッページのシミュレーション（設定可能）
    - 価格フィードのリプレイ（過去データ再生）
```

**MockAIProvider（テスト用AIプロバイダ）:**
```python
class MockAIProvider(BaseAIProvider):
    """テスト用。事前定義された構造化レスポンスを返す"""
    - 固定レスポンス返却（BUY/SELL/HOLD各パターン）
    - 不正JSONレスポンスの返却（エラーハンドリング検証）
    - レスポンス遅延のシミュレーション（タイムアウト検証）
```

**ペーパートレードモード:**
- MockExchangeをBaseExchangeの実装として差し込み、AIは本物を使用
- リアルタイム市場データに対してAIが判断 → 仮想発注 → 仮想損益追跡
- 本番投入前の戦略検証に使用

**safety_guard の重点テストケース:**
```
- ストップロス5%設定 → 含み損4.9%でHOLD、5.0%で強制決済
- 日次最大損失10% → 累計9.9%で警告、10.0%でトレーダー停止
- 最大ポジション3 → 3ポジション保有中に新規BUY → 拒否
- レバレッジ25倍 → 超過する注文量 → 自動縮小
- 複合: 日次損失8% + ストップロス接近 → 両方のガードが正しく動作
- 異常系: 価格データ欠損時のフェイルセーフ
- 【監査4】価格サニティ: 市場価格149.50に対し指値200.00提案 → 拒否
- 【監査4】価格サニティ: 市場価格149.50に対し指値149.55 → 許可（正常範囲）
```

**【監査2】Look-ahead Bias排除テスト:**
```
- 時刻T=12:00のContext生成時、12:00:01以降のOHLCVが含まれない事を検証
- 時刻T=12:00のContext生成時、12:00:01以降のTickerが含まれない事を検証
- 過去データリプレイ時、各ステップで「その時点で利用可能だったデータのみ」が渡される事を検証
- simulationモード時のDB書込先がsimulation_historyである事を検証
- simulationモードからliveモードへの切替時、simulation_historyのデータが混入しない事を検証
```

**【監査1】テナント隔離テスト:**
```
- ユーザーAのセッションでユーザーBのトレーダーが取得できない事を検証
- ユーザーAがユーザーBのtrader_idを指定してAPI呼出 → 403を検証
- TenantAwareSessionが全クエリにuser_idフィルタを自動付与する事を検証
```

**ディレクトリ構成:**
```
/backend/
  /tests/
    conftest.py              ... 共通fixture（MockExchange, MockAI, テストDB）
    /unit/
      test_safety_guard.py
      test_price_normalizer.py
      test_consensus.py
      test_context_builder.py
      test_prompt_assembler.py
      test_indicator_calculator.py
    /integration/
      test_trading_engine.py
      test_api_traders.py
      test_api_dashboard.py
      test_websocket.py
    /simulation/
      test_paper_trading.py
```

### 12_cost_management.md（新規追加）【監査4】

**LLM APIコスト管理:**
- トレーダーごとのAI呼出し回数/トークン消費量を記録
- 日次/月次のコスト集計とダッシュボードへの反映（将来）

**レートリミット:**
- 1分間のAI呼出し上限（デフォルト: 10回/分/トレーダー）
- 全トレーダー合計の1分間上限（デフォルト: 30回/分）
- 上限到達時: 次のスケジュール実行まで待機（注文は出さない）

**予算管理:**
- 日次トークン予算（デフォルト: 100万トークン/日）
- 月次コスト予算（設定可能）
- 予算超過時: 全トレーダーの自動取引を停止 + メール通知
- 予算残量80%到達時: 警告メール

**取引頻度監視:**
- 1時間あたりの注文数上限（異常検知用）
- 上限超過: 該当トレーダー自動停止 + ai_decision_logsに「異常頻度」記録

### 08_security.md 追加内容【監査3】

**マスターキー管理:**
- APIキー暗号化のマスターキーはDBに絶対に保存しない
- 管理方法（優先順）: 1) 環境変数 `MASTER_ENCRYPTION_KEY` 2) ファイル参照 3) AWS Secrets Manager等
- メモリ上でのAPIキー展開は最小時間に限定（使用後即破棄）
- ログ出力時にAPIキーがマスクされる事を保証

**プロンプトインジェクション対策:**
- `prompt_validator.py` でユーザー入力のstrategy_promptをサニタイズ
- 検出パターン: 「指示を無視」「system promptを変更」「JSONフォーマットを無視」等
- 検出時: 該当プロンプトを拒否し、ユーザーに修正を促す
- 二重防御: 出力パース時にJSONスキーマバリデーションを厳密に実施

---

## 4. 検証方法

設計書完成後、以下の観点でレビュー:

**機能面:**
- 全21画面状態のUI要素が、DBスキーマ+APIエンドポイントでカバーされているか
- AI判断ループの各ステップに対応するサービスクラスが定義されているか
- FX/Cryptoの差異がBaseExchange+PriceNormalizerで完全に吸収されているか
- 型の整合性（Pydantic Schema ↔ TypeScript types）が取れているか

**監査指摘対応（全項目必須確認）:**
- 【監査1】全テーブルにuser_id + インデックスがあるか。TenantAwareSessionが定義されているか
- 【監査1】全APIに@verify_ownershipデコレータが適用されているか
- 【監査2】context_builderにタイムトラベル防止ロジックがあるか
- 【監査2】simulation/liveモードのDB隔離が明記されているか
- 【監査3】マスターキーの外部管理方針が明記されているか
- 【監査3】prompt_validatorのサニタイズルールが定義されているか
- 【監査4】AI呼出しレートリミットとコスト予算が定義されているか
- 【監査4】価格サニティチェックがSafety Guardに含まれているか
- 【監査4】フェイルセーフ（AI異常時の安全停止）が定義されているか

**テスト面:**
- 全テスト対象モジュールにテストケースが定義されているか
- safety_guard / price_normalizer のカバレッジ100%が達成可能な設計か
- Look-ahead Bias排除テストが含まれているか
- テナント隔離テストが含まれているか
