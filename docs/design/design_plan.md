# AI Trading System 設計書作成プラン

## Context

Figma Slidesで定義されたUI仕様（5画面+サブ画面約21状態）と、
オーナー提供のExcel仕様書（AI_Trading_System_DevSheet.xlsx）、
および監査チームからの技術要件を統合し、**設計書**を作成する。
設計書は今後の実装の拠り所となるドキュメント。

**システムの核心（改定）**:
指標計算・セーフガード判定はPythonで決定論的に行う。
LLMは「最終判断」「曖昧さの解釈」「ルール生成」に限定する。
4段階パイプライン（方向判定→セットアップ→エントリー→退出管理）の
各段階にrule/aiAssist/aiFullの3モードを設け、
ruleモードでは完全にPython決定論的処理のみで動作する。

**優先順位（Excel仕様に準拠）**:
強制停止(SafeGuard) > 強制決済(SL/TP/最大保有) > 退出管理 > エントリー判定 > セットアップ > 方向・レジーム

---

## 確定済みの方針

- **認証**: DB構造はマルチユーザー対応。認証自体は初回は簡易的（フル装備は後回し）
- **AI判断ログ**: バックエンドのみ（DBに記録）。閲覧UIは作らない
- **FX取引所**: GMOコイン（REST API + WebSocket）
- **暗号通貨取引所**: bitbank
- **APIキー**: ユーザーごとに設定可能。UI未実装時は設定ファイルで対応可
- **設計書言語**: 日本語
- **取引対象**: FX（GMOコイン） + 暗号通貨（bitbank）
- **命名規則**: API/JSON は lowerCamelCase（Excel仕様に準拠）
- **時刻管理**: 内部UTC統一、UI表示のみJST

---

## 設計思想: 生存性・透明性・デバッグ容易性・チューニング支援

本システムはオーナーと開発者が別であり、私的利用が前提。
以下の4つの目的を達成するための設計原則を全設計書に適用する。

### 目的

```
0. 生存性: 利益最大化ではなく破綻回避を最上位目的とする
1. 透明性: オーナーが「なぜこの判断になったか」を追跡できる
2. デバッグ容易性: 問題発生時に原因箇所を素早く特定できる
3. チューニング支援: パラメータ調整の効果を比較検証できる
```

### 原則0: 生存性最優先（Survivability First）

本システムは「勝てるAI」ではなく「死なないAI」を設計目標とする。
オーナーのChatGPTでの検討を通じて確立された以下の認識を全設計に反映する:

```
前提認識:
  - 勝率の現実的期待値は48-58%（80%は幻想）
  - 勝率よりRR（リスクリワード比）とDD（ドローダウン）制御が10倍重要
  - AIで未来を当てるより、ロット制御・停止ルール・RR改善で生存確率が決まる
  - 勝率48%でもRR 1.4 + DD制御ありなら生き残る

生存性を担保する設計要素:
  1. ポジションサイジング: 1回の損失を資金のN%以内に制限（デフォルト1%）
  2. RR比の下限保証: RR < 0.8の注文はセーフガードでブロック
  3. DD制御: 日次/月次の最大損失率で強制停止
  4. 連敗停止: N回連続損失でクールダウン + ロット半減
  5. セーフガード最優先: いかなる判定結果よりもセーフガードが優先される
```

### 原則A: モジュールのインターフェース統一

各判定段階（M1〜M4）は統一インターフェース（BaseJudge）を実装する。
入力・出力・設定の3スキーマで境界を明確にし、
モジュール差替え時はインターフェースさえ合えばよい設計にする。

```python
class BaseJudge(ABC):
    def judge(self, input: JudgeInput, config: JudgeConfig) -> JudgeOutput
    def describe_config(self) -> dict  # 設定項目の説明を返す
```

各モジュールの出力には `_debug` フィールドを含める。
モジュール内部の判定経路・中間計算値を自由に出力できる場所とし、
オーナーの「把握」とデバッグの鍵とする。

```
出力例（M1 Direction）:
  {
    "trend": "UP",
    "confidence": 0.85,
    "reason_codes": ["ema_bullish_alignment", "adx_strong"],
    "_debug": {
      "ema20": 149.50, "ema50": 148.80, "ema200": 145.20,
      "adx_value": 28.5,
      "判定経路": "EMA3本順配列 → トレンドUP"
    }
  }
```

### 原則B: オーケストレーターによる自動ログ

モジュール側にログ実装を強制しない。
オーケストレーターが各モジュール呼出し時に自動記録する。

```
各呼出しで自動記録される情報:
  - execution_id（パイプライン実行単位の一意ID）
  - trader_id, pair, timestamp
  - stage（m1 / m2 / m3 / m4）
  - input_snapshot（JSON: 指標値・状態・前段階の結果）
  - output_snapshot（JSON: 判定結果 + _debug）
  - config_snapshot（JSON: 現在のパラメータ値）
  - elapsed_ms（処理時間）
```

これによりオーナーが追跡可能になる例:
- 「M1はUP判定したのにM2でセットアップ不成立。理由はRSIが70超で過熱判定」
- 「ADXの閾値を25→20に下げたらエントリー回数が1.5倍に増えた」

### 原則C: パラメータ変更の記録

Config変更時に変更前後と日時をDBに記録し、以下を可能にする:
- 「先週のパラメータに戻す」
- 「変更前後の成績比較」
- バックテスト時に「当時のパラメータ」で再実行

### やらないこと（過剰設計の排除）

```
- シャドウモード（並行比較実行）
- ベンダー向け開発ガイド
- モジュールの動的ロード/プラグイン機構
- 複雑なバージョン管理（設定変更履歴のみで足りる）
```

---

## 監査指摘事項（設計書に反映必須）

### 監査1: マルチテナント隔離（情報取り違え防止）
- **リスク**: ユーザーAの注文がユーザーBの取引所に飛ぶ
- **対策1**: SQLAlchemy Session生成時に`user_id`を自動フィルタするインターセプター → `07_database_schema.md`
- **対策2**: 全APIで「trader_idがリクエストuser_idに属するか」検証する共通デコレータ → `08_api_specification.md`

### 監査2: Look-ahead Bias防止（先読みバイアス）
- **リスク**: シミュレーション/バックテストで未来データが判定ロジックに漏洩
- **対策1**: State Builderが時刻T以降のデータを物理的に渡さない「タイムトラベル防止」テスト → `13_testing_strategy.md`
- **対策2**: シミュレーションDB書込先の物理隔離 → `09_backtest_simulation.md`

### 監査3: 鍵管理とプロンプトインジェクション
- **リスク1**: マスターキー（APIキー復号鍵）がDBに保存される
- **対策1**: マスターキーは環境変数 or 外部シークレット管理で保持。DBには絶対に置かない → `11_security.md`
- **リスク2**: strategy_promptに「指示を無視して全力買い」等の悪意ある命令が混入
- **対策2**: Prompt Assemblerにサニタイズ/バリデーション層を追加 → `05_ai_integration.md`

### 監査4: AIの暴走・コスト爆発防止
- **リスク1**: AIが異常な頻度で注文を提案 / LLM APIコスト爆発
- **対策1**: AI呼出しのレートリミット（1分間上限、日次トークン予算） → `14_cost_management.md`
- **リスク2**: 市場価格から大幅に乖離した指値を提案
- **対策2**: セーフガードに「価格サニティチェック」追加 → `03_safeguard_engine.md`
- **リスク3**: AIが想定外JSONを返す / APIタイムアウト
- **対策3**: フェイルセーフ定義（異常時はHOLD、新規注文禁止） → `05_ai_integration.md`

---

## 1. アーキテクチャ変更の経緯と影響

### 1-1. 旧アーキテクチャ（AI自律型）→ 新アーキテクチャ（ルール主導）

旧設計ではAIに自律的にトレードを委任する構成だった。
オーナーからのExcel仕様により、以下に転換:

- Python決定論的処理が主役（指標計算、セーフガード、ruleモード判定）
- AIは補助的役割（aiAssistモード: ルール判定後の最終確認、aiFullモード: 非推奨）
- AI呼出しはイベント駆動（定期スケジュールではなく、判定が必要な時のみ）
- セーフガードが6項目から40項目に大幅拡張（6カテゴリ）
- 4段階パイプラインによる段階的判定（旧: AIが一括判断）

### 1-2. 新アーキテクチャのデータパイプライン

```
Market Data Ingest（価格データ受信）
  → Bar Builder（ティック→OHLC足生成: M1/M5/M15/M30/H1/H4/D1）
  → Indicator Engine（インクリメンタル更新）
      EMA(20/50/200), ADX(14), ATR(14), Donchian(20),
      RSI(14), Bollinger(20,2), Swing
  → State Builder（数値→状態ラベル変換）
      trend: UP/DOWN/NEUTRAL
      regime: trend/range
      volatility: low/normal/high/extreme
  → Guard Engine（40項目セーフガード評価）
  → Decision Orchestrator（4段階パイプライン）
      M1: 方向・レジーム判定
      M2: セットアップ判定
      M3: 実行・エントリー
      M4: 退出管理
      MX: 統合判定（all/dir+setup/score）
  → Execution Engine（注文発行・約定確認）
  → Audit/Logging（全判断の証跡保管）
```

### 1-3. 旧設計からの影響分析

旧02_ai_trading_engine.md（単一ファイル）は以下4ファイルに分割:
- 02_data_pipeline.md: データ取得→指標計算→状態変換
- 03_safeguard_engine.md: 40項目のガードエンジン
- 04_decision_pipeline.md: 4段階パイプライン+統合判定
- 05_ai_integration.md: AI呼出条件/プロンプト/パース/フォールバック

旧06_realtime_data_flow.md は新02_data_pipeline.mdに統合（重複解消）。
旧11_testing_strategy.md のバックテスト部分は新09_backtest_simulation.mdに独立。

バックテストが「将来拡張」から「設計対象」に昇格した理由:
- ruleモードは完全に決定論的 → 再現可能なバックテストが実施可能
- Excel仕様のテストチェックリストが過去データ再生を前提としている
- ルール主導になったことで、バックテストの実用的価値が大幅に向上

---

## 2. Figma仕様 vs 新Excel仕様 齟齬分析

### 2-1. DBスキーマの齟齬

旧技術要件は4テーブル→Figma UIから14テーブルを導出していたが、
Excel仕様により追加テーブルが必要:

- `safeguard_configs`: トレーダーごとの40項目セーフガード設定
- `model_stage_configs`: 4段階モデル設定（M1〜M4+MX、41項目）
- `indicator_snapshots`: 指標スナップショット（バックテスト用）
- `backtest_runs`: バックテスト実行記録
- `backtest_trades`: バックテストのシミュレート取引
- `historical_ohlcv`: ヒストリカルデータ保存
- `pipeline_logs`: パイプライン実行ログ（設計思想: 自動ログ）
- `config_changes`: パラメータ変更履歴（設計思想: チューニング支援）

### 2-2. UI画面への影響

トレーダー設定画面が最も大きな影響を受ける（41項目のモデル設定追加）。

**UI方針（確定）**: Figma画面はオーナー側で更新しない。
現在のFigma画面を基本再現し、仕様と不整合がある箇所は開発側で画面を調整する。
設計書フェーズでは画面情報を意識しつつ、画面の具体的な修正は実装フェーズで行う。

影響度サマリ:
- トレーダー設定画面: 大（再設計レベル。41項目追加によりタブ構造への変更が必要）
- ダッシュボード（トレーダーパネル）: 中（パイプライン状態、ガード状態表示）
- ダッシュボード（チャート）: 中（指標プリセット、30分足追加）
- システム設定: 中（セーフガード/コスト管理/経済指標の新規セクション）
- 取引履歴: 小〜中（4段階判定結果、ガード発動履歴）
- 通知設定: 小（通知トリガー種別追加）
- マーケットウォッチ: 小（スプレッド表示、セッション表示）
- 新規画面: バックテスト、パイプラインログ、設定変更履歴（Figmaテイスト踏襲で新規設計）

### 2-3. APIエンドポイントへの影響

旧設計の約35エンドポイントに加え、以下が追加:
- セーフガード設定CRUD
- モデルステージ設定CRUD
- バックテスト実行・結果取得
- ヒストリカルデータ取得
- パイプラインログ照会（設計思想: 透明性）

---

## 3. 設計書の構成と作業手順

`/docs/design/` に以下15ファイルを作成する。

### ファイル一覧

```
00_executive_summary.md          ... プロジェクト概要・アーキテクチャ全体像
01_screen_specification.md       ... 全画面仕様（Figma + Excel仕様統合）
02_data_pipeline.md              ... データソース・取得・Bar Builder・指標計算・状態変換
03_safeguard_engine.md           ... 40項目6カテゴリのセーフガード設計
04_decision_pipeline.md          ... 4段階パイプライン(M1〜M4) + 統合判定(MX) + 設計思想
05_ai_integration.md             ... AI呼出条件・プロンプト組立・パース・フォールバック
06_exchange_abstraction.md       ... BaseExchange + PriceNormalizer + GMOコイン/bitbank固有
07_database_schema.md            ... 全テーブル定義（20テーブル超）
08_api_specification.md          ... REST API + WebSocket 全エンドポイント
09_backtest_simulation.md        ... ヒストリカルデータソース・実行エンジン・評価指標
10_frontend_architecture.md      ... コンポーネント・状態管理
11_security.md                   ... 認証・暗号化・鍵管理・プロンプトインジェクション対策
12_directory_structure.md        ... ディレクトリ構成
13_testing_strategy.md           ... テスト方針・単体テスト設計
14_cost_management.md            ... LLM APIコスト管理・レートリミット
15_implementation_phases.md      ... 実装フェーズ計画
```

### 作成順序（依存関係順）

**Step 1（最重要・データの土台）**
```
02_data_pipeline.md
  GMOコイン API / bitbank APIのデータソース仕様から、
  Bar Builder、Indicator Engine、State Builderまでの
  全パイプラインを定義。後続の全設計書の入力データを規定する。
```

**Step 2（判定ロジック）**
```
03_safeguard_engine.md    ... 判定に先立つ安全チェック（40項目）
04_decision_pipeline.md   ... 4段階パイプライン + BaseJudgeインターフェース
                              + オーケストレーター自動ログ設計
```

**Step 3（AI・外部接続）**
```
05_ai_integration.md      ... 判定パイプラインのAIプラグイン
06_exchange_abstraction.md ... 執行レイヤー（GMOコイン/bitbank/Mock）
```

**Step 4（永続化・API）**
```
07_database_schema.md     ... Step1-3 + pipeline_logs + config_changes
08_api_specification.md   ... DBスキーマ確定後にエンドポイント設計
```

**Step 5（検証基盤）**
```
09_backtest_simulation.md ... パイプライン設計確定後にバックテスト設計
13_testing_strategy.md    ... バックテスト設計と連携したテスト方針
```

**Step 6（残り）**
```
00_executive_summary.md        ... 全体像は最後にまとめる
01_screen_specification.md     ... オーナーからのUI方針回答後
10_frontend_architecture.md    ... 画面仕様確定後
11_security.md                 ... 監査指摘対応の集約
12_directory_structure.md      ... 全サービス確定後
14_cost_management.md          ... AI統合設計確定後
15_implementation_phases.md    ... 全設計書完成後
```

---

## 4. 各設計書の内容概要

### 02_data_pipeline.md（最優先）

**ライブデータソース:**

```
FX（GMOコイン API）
  - 接続方式: REST API（Public + Private） + WebSocket
  - 認証: APIキー + HMAC署名
  - 価格データ: Bid/Ask取得可
  - OHLCデータ: KLine API（OHLCV）
  - 対応通貨ペア: USD/JPY, EUR/JPY, GBP/JPY, AUD/JPY 等14ペア
  - レートリミット: 公式非公開（緩い）
  - 注文種別: MARKET / LIMIT / STOP / OCO / IFD / IFDOCO
  - ストリーミング: WebSocket（板情報、ティック）
  - ヒストリカルデータ: 2023/10以降
  - 注意: トレーリングストップはAPI非提供（システム側で実装）
  - 注意: 高頻度取引でのアカウント凍結リスクあり（頻度設計に注意）

暗号通貨（bitbank）
  - bitbank Public API: REST + WebSocket
  - 必要データ: ティック、OHLCV、板情報、スプレッド
  - 制約: レートリミット、提供時間足
```

**データソース抽象化:**
```python
class BaseDataProvider(ABC):
    async def get_ohlcv(pair, timeframe, limit) -> list[OHLCV]
    async def get_ticker(pair) -> Ticker
    async def get_spread(pair) -> Spread
    async def subscribe_ticks(pairs, callback) -> None
    async def get_historical_ohlcv(pair, timeframe, start, end) -> list[OHLCV]
```

**Bar Builder:**
- ティックデータからOHLC足を生成（M1/M5/M15/M30/H1/H4/D1）
- 足確定イベントの発行（Indicator Engineへのトリガー）
- 不完全足（現在進行中の足）の扱い
- GMOコイン固有: Bid/Ask価格からMid価格を算出する変換層

**Indicator Engine（インクリメンタル更新）:**
- EMA(20/50/200): 指数移動平均
- ADX(14): トレンド強度
- ATR(14): ボラティリティ
- Donchian(20): チャネルブレイクアウト
- RSI(14): 相対力指数
- Bollinger(20,2): ボリンジャーバンド
- Swing: スイングハイ/ロー検出
- 全指標はインクリメンタル（1本追加で再計算、全履歴不要）

**State Builder（数値→状態ラベル変換）:**
```json
{
  "trend": "UP|DOWN|NEUTRAL",
  "regime": "trend|range",
  "volatility": "low|normal|high|extreme",
  "tradeAllowed": true,
  "indicators": { "ema20": 149.50, "adx14": 28.5, ... }
}
```

**データ品質管理:**
- 欠損検出: 足抜け、ティックギャップ
- 異常値検出: スパイク、ゼロ値
- タイムゾーン正規化: UTC統一
- 補完ルール: 前値補完 or 線形補間（指標種別ごとに定義）

### 03_safeguard_engine.md

**40項目・6カテゴリ（Excel仕様SG-001〜SG-040に準拠）:**

```
資金保護（SG-001〜SG-009）
  - 日次/月次最大損失率での停止
  - 最大ドローダウン制御
  - 利益目標達成時の停止
  - 連続損失カウント→クールダウン→ロット半減

市場異常検知（SG-010〜SG-018）
  - スプレッド監視・閾値超過で停止
  - ATR急増（通常の2倍等）検知
  - 急変動（1分間X pips以上）検知
  - 【監査4】価格サニティチェック

取引時間制御（SG-019〜SG-026）
  - 東京/ロンドン/NYセッション時間管理
  - セッション開始後/終了前バッファ
  - ボラティリティ低下時の停止

経済指標フィルター（SG-027〜SG-031）
  - 重要指標発表前後の取引停止
  - 重要度フィルタ（high/medium/low）
  - 対象通貨ペアとのマッチング
  - データソース: 経済指標カレンダーAPI

レジーム保護（SG-032〜SG-034）
  - トレンド崩壊検知→停止
  - ADX低下→レンジ移行→停止
  - レジーム変化時のポジション扱い

実行保護（SG-035〜SG-042）
  - 最大同時ポジション数制限
  - 同方向ポジション制限
  - 相関通貨ペアの重複禁止
  - AI応答遅延時のフォールバック
  - AI出力異常時のフォールバック
  - confidence未達時のフォールバック
  - 【生存性】RRサニティチェック（RR < 下限値の注文をブロック）
  - 【生存性】ポジションサイズ上限チェック（1回リスクが資金N%を超える注文をブロック）
```

**Guard Engineの設計:**
- 全ガードは優先度順に評価（SG-IDの若番が高優先度ではない、カテゴリ内優先度で管理）
- 評価結果: PASS / WARN / BLOCK / HALT
- BLOCK: 当該注文を拒否
- HALT: トレーダー自体を停止
- 全評価結果をログに記録（監査証跡）

### 04_decision_pipeline.md

**設計思想の適用:**

BaseJudgeインターフェース:
```python
class BaseJudge(ABC):
    def judge(self, input: JudgeInput, config: JudgeConfig) -> JudgeOutput
    def describe_config(self) -> dict

# 各段階の実装
class M1DirectionJudge(BaseJudge): ...
class M2SetupJudge(BaseJudge): ...
class M3EntryJudge(BaseJudge): ...
class M4ExitManager(BaseJudge): ...
```

全モジュール出力に `_debug` フィールドを含める:
```
_debug: {
  "中間計算値": { ... },
  "判定経路": "条件A=True → 条件B=False → 結果X",
  "閾値との距離": { "adx": "28.5 (閾値25を3.5超過)" }
}
```

オーケストレーターの自動ログ:
- 各モジュール呼出し時にinput/output/config/elapsed_msを自動記録
- モジュール側にログ実装を強制しない
- pipeline_logsテーブルに保存（execution_id単位でグループ化）

**4段階パイプライン（Excel仕様M1〜M4+MXに準拠）:**

```
M1: 方向・レジーム判定（11設定項目）
  入力: D1/H4/H1の指標・状態
  出力: { trend, regime, volatility, tradeAllowed, confidence, _debug }
  モード: rule → EMA/ADX/ATRの数値ルールで判定
          aiAssist → ルール判定後、AIに最終確認
          aiFull → AIが全判断（非推奨）

M2: セットアップ判定（8設定項目）
  入力: H1/M30/M15の指標 + M1の結果
  出力: { setupValid, setupType, probability, confidence, _debug }
  戦略プリセット: trendFollow / pullback / breakout / meanReversion
  モード: rule / aiAssist / aiFull

M3: 実行・エントリー（8設定項目 + ポジションサイジング）
  入力: M5/M1の指標 + M1/M2の結果 + 口座残高・リスク設定
  出力: { entry, entryType, tpPips, slPips, lotSize, riskRewardRatio, confidence, _debug }
  注文方式: market / limit
  TP/SL方式: fixedPips / atr
  モード: rule / aiAssist / aiFull

  【生存性】ポジションサイジング計算（M3出力の必須処理）:
    lotSize = (口座残高 × riskPercent) / (slPips × pipValue)
    riskRewardRatio = tpPips / slPips
    ※ riskRewardRatio < rrMinThreshold（デフォルト0.8）の場合 → 注文をブロック
    ※ lotSize算出後、口座の最大ロット制限・取引所の最小ロット制約でクリップ
    ※ この計算はモード（rule/aiAssist/aiFull）に関わらず必ず実行される

M4: 退出管理（9設定項目）
  入力: 現在ポジション + 最新指標
  出力: { action, tpAdjustPips, trailMode, confidence, _debug }
  機能: ブレイクイーブン / トレーリングストップ / 部分利確 / 最大保有時間
  モード: rule / aiAssist / aiFull
```

**MX: 統合判定ロジック（5設定項目）:**
```
判定方式:
  all       → M1〜M4全てPASSで実行
  dir+setup → M1+M2がPASSならM3以降を実行
  score     → 各段階のconfidenceに重みを掛けて合算、しきい値で判定

スコア方式の例:
  重み: M1=0.3, M2=0.3, M3=0.25, M4=0.15
  しきい値: 0.65
  算出: 0.85*0.3 + 0.72*0.3 + 0.80*0.25 + 0.70*0.15 = 0.776 → PASS
```

**パイプライン制御フロー:**
- M1がBLOCK → M2以降はスキップ（Guard Engineと同様の早期終了）
- 各段階の実行間隔はトレーダー設定で制御
- イベント駆動: 足確定 or ポジション変化をトリガーに評価

### 05_ai_integration.md

**AI呼出条件（aiAssist/aiFullモード時のみ）:**
- ruleモードでは一切AIを呼ばない
- aiAssistモード: ルール判定結果をコンテキストとしてAIに渡し、最終確認を求める
- aiFullモード: 市場データとコンテキストをAIに渡し、判断を委ねる（非推奨）

**プロンプト構成（4段階それぞれに専用プロンプト）:**
```
各段階共通構造:
  Layer 1: システムプロンプト（JSON出力強制、安全制約）
  Layer 2: ユーザー戦略プロンプト（strategy_prompt、max2000文字）
  Layer 3: 構造化コンテキスト（指標値+状態+ポジション）
  Layer 4: ruleモード判定結果（aiAssist時のみ追加）
```

**AI出力スキーマ（4段階、Excel仕様に準拠）:**
```json
Direction: {"trend":"UP","regime":"trend","volatility":"normal",
            "tradeAllowed":true,"confidence":0.85,"reason_codes":[...]}
Setup:     {"setupValid":true,"setupType":"pullback",
            "probability":0.72,"confidence":0.72,"reason_codes":[...]}
Entry:     {"entry":"BUY","entryType":"market","tpPips":15,"slPips":20,
            "confidence":0.80,"reason_codes":[...]}
Exit:      {"action":"EXTEND_TP","tpAdjustPips":5,"trailMode":"ON",
            "confidence":0.70,"reason_codes":[...]}
```

**LLMパラメータ推奨（Excel仕様に準拠）:**
- temperature: 0〜0.2（決定論的出力を重視）
- timeout: 3〜5秒
- max_tokens: 300

**フェイルセーフ（AI異常時）:**【監査4】
- 不正JSON応答 → HOLD（新規注文禁止、既存ポジション維持）
- APIタイムアウト → HOLD + アラート通知
- APIエラー(429/500等) → HOLD + 次回トリガーまで待機
- 全AIプロバイダ障害 → トレーダー自動停止 + 緊急メール通知
- 原則: 「判断できない時は何もしない」が最も安全

**プロンプトインジェクション対策:**【監査3】
- Layer 2（ユーザー戦略プロンプト）をサニタイズ
- 検出パターン: 「指示を無視」「system promptを変更」「JSONフォーマットを無視」等
- 出力パース時にJSONスキーマバリデーションを厳密実施

### 06_exchange_abstraction.md

```python
class BaseExchange(ABC):
    async def get_ticker(pair) -> Ticker
    async def get_ohlcv(pair, timeframe, limit) -> list[OHLCV]
    async def place_order(pair, side, amount, type, price?) -> Order
    async def cancel_order(order_id) -> bool
    async def get_order_status(order_id) -> OrderStatus
    async def get_positions() -> list[Position]
    async def close_position(position_id) -> Order
    async def get_balance() -> Balance
    async def subscribe_price_stream(pairs, callback) -> None
```

- PriceNormalizer: FXのpip計算 vs Cryptoの小数点計算を統一
- PositionSizer: 口座残高・リスク%・SL幅からロットサイズを算出する共通モジュール
  - 入力: balance, riskPercent, slPips, pipValue, minLot, maxLot
  - 出力: lotSize（クリップ済み）
  - FX/Cryptoで pipValue の算出方法が異なるため PriceNormalizer と連携
  - 算出結果は _debug に記録（透明性確保）
- MockExchange: テスト・ペーパートレード・バックテスト用の仮想取引所

**GMOコイン実装（GmoFxExchange）:**
- GMOコイン API (REST + WebSocket) をBaseExchangeインターフェースに適合
- 認証: APIキー + HMAC署名（タイムスタンプベース）
- 注文: Market/Limit/Stop/OCO/IFD/IFDOCO
- トレーリングストップ: APIに非提供。M4退出管理でシステム側実装（STOP注文の変更で実現）
- 部分利確: 部分決済に対応（ポジション数量を指定して一部決済可能）
- 高頻度取引制限: 過度な注文頻度でアカウント凍結リスクあり。注文間隔に余裕を持たせる設計

**bitbank実装（BitbankExchange）:**
- bitbank API (REST + WebSocket) をBaseExchangeインターフェースに適合

### 07_database_schema.md

**【監査1対応】マルチテナント隔離:**
- 全テーブルに`user_id`カラム必須化 + インデックス設計
- SQLAlchemy Session生成時にuser_idを自動フィルタする`TenantAwareSession`
- 直接SQLを書く場合も必ずuser_id条件を含むことをレビュー基準に

**テーブル一覧（20テーブル超）:**

基本テーブル:
- `users`: ユーザー管理
- `traders`: トレーダー基本設定（T-001〜T-012）
- `model_stage_configs`: 4段階モデル設定（M1〜M4+MX、41項目）
- `safeguard_configs`: セーフガード設定（SG-001〜SG-040）
- `positions`: 保有ポジション
- `trade_history`: 取引履歴
- `ai_decision_logs`: AI判断履歴（4段階分）
- `safeguard_logs`: セーフガード発動履歴

設定テーブル:
- `exchange_configs`: 取引所APIキー（ユーザーごと）
- `ai_model_configs`: AI APIキー+モデル設定（ユーザーごと）
- `system_default_prompts`: 4段階のデフォルトプロンプト
- `notification_emails`: 通知先メールアドレス
- `daily_notification_configs`: デイリー通知設定

UI永続化テーブル:
- `market_watch_configs`: マーケットウォッチ設定
- `chart_configs`: チャートパネル設定

バックテスト・データテーブル:
- `historical_ohlcv`: ヒストリカルOHLCVデータ
- `backtest_runs`: バックテスト実行記録
- `backtest_trades`: バックテストシミュレート取引
- `simulation_history`: ペーパートレード履歴（本番DBと隔離）【監査2】

**パイプライン可観測性テーブル（設計思想）:**
- `pipeline_logs`: パイプライン実行ログ
  - execution_id, trader_id, pair, timestamp
  - stage (m1/m2/m3/m4)
  - input_snapshot (JSON), output_snapshot (JSON), config_snapshot (JSON)
  - elapsed_ms
  - 用途: 透明性確保、デバッグ、チューニング効果の比較
- `config_changes`: パラメータ変更履歴
  - trader_id, stage, config_before (JSON), config_after (JSON)
  - changed_at, changed_by (user_id), change_reason (任意コメント)
  - 用途: 「先週のパラメータに戻す」「変更前後の成績比較」

### 08_api_specification.md

**【監査1対応】全エンドポイントのオーナーシップ検証:**
- `trader_id`を受け取る全APIに共通デコレータ`@verify_ownership`を適用
- 不正アクセスは403 Forbidden

**エンドポイントカテゴリ（約40+エンドポイント）:**
- Dashboard: summary, close-all, stop-all, start-all
- Traders: CRUD + start/stop/close-all
- Model Stages: 4段階モデル設定CRUD（新規）
- Safeguards: セーフガード設定CRUD（新規）
- Market Watch: CRUD + reorder
- Charts: OHLCV + indicators + markers
- Notifications: SMTP設定, メールCRUD, テスト送信, デイリー設定
- History: 一覧 + チャートデータ + CSV出力
- Backtest: 実行開始 + 結果取得 + 一覧（新規）
- Pipeline Logs: 実行ログ照会 + フィルタ（新規、設計思想: 透明性）
- Settings: 取引所API, AI API, システム状態
- Account: 情報取得/更新, ログアウト
- WebSocket: prices, trader_updates, alerts, pipeline_status（新規）

### 09_backtest_simulation.md（新規）

**ヒストリカルデータソース:**

```
FX（GMOコイン API）:
  - KLine APIで過去OHLCVを取得
  - ヒストリカルデータ提供開始: 2023/10以降（約2.5年分）
  - 制約: 長期ヒストリカルデータの蓄積が限定的

  補助ソース（GMOコインのヒストリカルが不足する場合）:
    - HistData.com: 一部通貨ペアの無料ティックデータ
    - Dukascopy: 高精度ティックデータ（有料）
    - 自前蓄積: ライブデータを継続保存して長期データを構築

暗号通貨（bitbank）:
  - bitbank API: OHLCV取得可能（期間制限あり）
  - CryptoCompare API: 長期ヒストリカルデータ
  - 自前蓄積: ライブデータを継続保存して蓄積

共通:
  - 保存形式: DBテーブル（historical_ohlcv）
  - 取得・蓄積の自動化（日次バッチ or 継続ストリーミング保存）
  - データ品質チェック（欠損、異常値、TZ統一）
```

**バックテスト実行エンジン:**
```
- 時刻Tを1ステップ（1足）ずつ進める制御
- 各ステップで完全なパイプラインを実行:
    Indicator Engine → State Builder → Guard Engine
    → Decision Orchestrator → Execution Engine（MockExchange）
- 全ステップでpipeline_logsに記録（本番と同じ可観測性を確保）
- Look-ahead Bias防止: 時刻T以降のデータは物理的にアクセス不可【監査2】
- スリッページ・約定遅延のモデリング（設定可能）
```

**ruleモード vs aiAssistモードのバックテスト:**
```
ruleモード:
  - 完全再現可能（同一入力→同一出力）
  - 大量データで高速実行可能（API呼出なし）
  - パラメータ最適化（グリッドサーチ等）に利用可能
  - config_changesと組み合わせて「当時のパラメータで再実行」が可能

aiAssistモード:
  - AI応答は非決定的 → 完全再現は不可
  - 方式1: AI応答をモック化（固定レスポンスでパイプライン検証）
  - 方式2: AI応答を記録・再生（過去のAI判断をリプレイ）
  - コスト考慮: バックテスト中のAI API呼出は大量になるため、
    モック化を基本とし、本番AI呼出は限定的に使用
```

**評価指標:**
- 損益（PnL）、勝率、プロフィットファクター
- 最大ドローダウン、シャープレシオ、カルマーレシオ
- トレード数、平均保有時間
- 平均RR比（実現値）、RR分布
- セーフガード発動回数・影響の統計（RRブロック・ポジションサイズブロック含む）
- 【生存性】破綻確率推定: 勝率・RR・1回リスク%・月トレード数から算出

**シミュレーション環境の隔離:**【監査2】
- 環境変数 `TRADING_MODE=live|simulation|backtest` で切替
- バックテスト時: `backtest_trades`テーブルに書込
- シミュレーション時: `simulation_history`テーブルに書込
- 本番`trade_history`テーブルには触れない

### 11_security.md

**マスターキー管理:**【監査3】
- APIキー暗号化のマスターキーはDBに絶対に保存しない
- 管理方法（優先順）: 1) 環境変数 2) ファイル参照 3) AWS Secrets Manager等
- ログ出力時にAPIキーがマスクされる事を保証

**プロンプトインジェクション対策:**【監査3】
- 05_ai_integration.md のPrompt Assemblerで対策
- 二重防御: 出力パース時にJSONスキーマバリデーション

### 12_directory_structure.md

```
/ai_trading_system/
  /docs/
    /design/                  ... 設計書（15ファイル）
    AI_Trading_System_DevSheet.xlsx
  /backend/
    /app/
      main.py
      config.py               ... Pydantic BaseSettings（環境モード管理含む）
      /api/
        /routes/              ... 全エンドポイント
        /middleware/           ... TenantAwareSession, verify_ownership【監査1】
      /models/                ... SQLAlchemy モデル（20テーブル超）
      /schemas/               ... Pydantic スキーマ（Input/Output/Configスキーマ含む）
      /services/
        /pipeline/            ... data_ingest, bar_builder, indicator_engine,
                                  state_builder
        /safeguard/           ... guard_engine, guard_rules
        /decision/            ... base_judge, orchestrator,
                                  m1_direction, m2_setup, m3_entry, m4_exit,
                                  mx_integration
        /ai/                  ... base_provider, openai, gemini, claude,
                                  prompt_assembler, prompt_validator, response_parser
        /exchange/            ... base, mock, gmo_fx, bitbank, price_normalizer,
                                  position_sizer
        /backtest/            ... engine, data_loader, evaluator
        /notification/        ... email_service, daily_report
        /cost/                ... rate_limiter, budget_tracker【監査4】
      /db/                    ... session, migrations (Alembic)
    requirements.txt
  /frontend/
    /src/
      /components/            ... 画面別コンポーネント
      /hooks/                 ... WebSocket, API フック
      /lib/                   ... api client, types
      /store/                 ... 状態管理
  /backend/tests/
    conftest.py               ... 共通fixture
    /unit/
      test_indicator_engine.py
      test_state_builder.py
      test_guard_engine.py
      test_decision_orchestrator.py
      test_m1_direction.py     ... BaseJudge実装の単体テスト
      test_price_normalizer.py
      test_position_sizer.py     ... ロット算出・RR検証の単体テスト
      test_prompt_assembler.py
    /integration/
      test_pipeline_full.py    ... パイプライン全体 + 自動ログ記録の検証
      test_api_traders.py
      test_api_dashboard.py
      test_websocket.py
    /backtest/
      test_backtest_engine.py
      test_look_ahead_bias.py  ... 【監査2】
    /simulation/
      test_paper_trading.py
```

### 13_testing_strategy.md

**テストの特殊性（改定）**:
ルール主導になったことで、決定論的処理のテストカバレッジを最大化できる。
AIの非決定性はaiAssist/aiFullモードに限定されるため、
ruleモードのパイプライン全体を厳密にテストする。

**モジュール別テスト方針と優先度:**

| モジュール | 優先度 | テスト方針 |
|---|---|---|
| guard_engine | **最高** | 40ルール全て・境界値・競合・優先度。バグ=実損害 |
| position_sizer | **最高** | ロットサイズ算出の数学的正確性・RR検証・上下限クリップ。バグ=過大リスク |
| price_normalizer | **最高** | FX pip計算・Crypto小数点・損益計算の数学的正確性 |
| indicator_engine | **最高** | 全指標の計算精度を既知データで検証。バグ=誤判断 |
| state_builder | 高 | 数値→状態変換の境界値テスト |
| decision_orchestrator | 高 | 4段階制御フロー・統合判定・自動ログ記録の検証 |
| m1〜m4 judges | 高 | BaseJudgeインターフェース準拠・_debug出力の検証 |
| prompt_assembler | 高 | 4段階プロンプト合成・サニタイズ検証 |
| order_executor | 高 | MockExchange経由の発注・約定・エラー |
| gmo_fx_exchange | 高 | GMOコインAPI固有の制約（高頻度制限、注文種別）の検証 |
| bar_builder | 中 | ティック→足変換の正確性 |
| backtest_engine | 中 | Look-ahead Bias排除テスト【監査2】 |
| API routes | 中 | FastAPI TestClient でリクエスト/レスポンス検証 |

**テスト基盤:**
- フレームワーク: `pytest` + `pytest-asyncio`
- モック: `unittest.mock` + MockExchange + MockAIProvider + MockDataProvider
- DB: SQLite in-memory（テスト専用）
- カバレッジ: guard_engine, position_sizer, price_normalizer, indicator_engine は100%必須

**【監査2】Look-ahead Bias排除テスト:**
```
- 時刻T=12:00のState Builder実行時、12:00:01以降のOHLCVが含まれない事を検証
- バックテスト中、各ステップで「その時点で利用可能だったデータのみ」が渡される事を検証
- backtest/simulationモード時のDB書込先が本番テーブルでない事を検証
```

**【監査1】テナント隔離テスト:**
```
- ユーザーAのセッションでユーザーBのトレーダーが取得できない事を検証
- ユーザーAがユーザーBのtrader_idを指定してAPI呼出 → 403を検証
- TenantAwareSessionが全クエリにuser_idフィルタを自動付与する事を検証
```

**設計思想の検証:**
```
- オーケストレーターが各段階でpipeline_logsに記録する事を検証
- 全JudgeモジュールがBaseJudgeインターフェースに準拠する事を検証
- _debugフィールドが出力に含まれる事を検証
- config_changesにパラメータ変更が記録される事を検証
```

### 14_cost_management.md【監査4】

**LLM APIコスト管理:**
- トレーダーごと・段階ごとのAI呼出し回数/トークン消費量を記録
- 日次/月次のコスト集計

**レートリミット:**
- 1分間のAI呼出し上限（デフォルト: 10回/分/トレーダー）
- 全トレーダー合計の1分間上限（デフォルト: 30回/分）
- 上限到達時: 次のトリガーまで待機（注文は出さない）

**予算管理:**
- 日次トークン予算（デフォルト: 100万トークン/日）
- 月次コスト予算（設定可能）
- 予算超過時: 全トレーダーの自動取引を停止 + メール通知
- 予算残量80%到達時: 警告メール

**ruleモード活用によるコスト最適化:**
- ruleモードではAI APIコストゼロ
- aiAssistモードでもAI呼出しは「最終確認」のみ（トークン消費を抑制）
- バックテスト時はモック化でAPI呼出を回避

---

## 5. 検証方法

設計書完成後、以下の観点でレビュー:

**機能面:**
- Excel仕様の全設定項目（T-001〜T-012, M1-001〜MX-005, SG-001〜SG-040）が
  DBスキーマ + API + UIでカバーされているか
- 4段階パイプラインの各ステップに対応するサービスクラスが定義されているか
- FX/Cryptoの差異がBaseExchange + BaseDataProvider + PriceNormalizerで吸収されているか
- GMOコイン API / bitbank APIの制約（高頻度制限、注文種別等）が設計に反映されているか
- バックテスト基盤がruleモードのパイプライン全体をカバーしているか

**設計思想の検証:**
- 【生存性】PositionSizerが全注文パスに組み込まれ、バイパス不可であるか
- 【生存性】RR比の下限チェックがセーフガードに含まれ、M3出力で必ず検証されるか
- 【生存性】ポジションサイズが口座残高×リスク%から算出され、固定ロットでないか
- 全JudgeモジュールがBaseJudgeインターフェースを実装しているか
- 全モジュール出力に_debugフィールドが定義されているか
- オーケストレーターがpipeline_logsに全段階のinput/output/configを記録しているか
- config_changesテーブルでパラメータ変更の追跡が可能か
- モジュール差替えがインターフェース準拠のみで可能か

**監査指摘対応（全項目必須確認）:**
- 【監査1】全テーブルにuser_id + インデックス。TenantAwareSession定義
- 【監査1】全APIに@verify_ownershipデコレータ
- 【監査2】State Builderにタイムトラベル防止ロジック
- 【監査2】simulation/backtest/liveモードのDB隔離
- 【監査3】マスターキーの外部管理方針
- 【監査3】prompt_validatorのサニタイズルール
- 【監査4】AI呼出しレートリミットとコスト予算
- 【監査4】価格サニティチェックがセーフガードに含まれる
- 【監査4】フェイルセーフ（AI異常時の安全停止）定義

**テスト面:**
- 全テスト対象モジュールにテストケースが定義されているか
- guard_engine / position_sizer / price_normalizer / indicator_engine のカバレッジ100%達成可能か
- 【生存性】PositionSizer: 各通貨ペアでのロット算出精度・境界値・最小/最大ロットクリップの検証
- 【生存性】RRサニティチェック: RR < 下限値の注文がブロックされることの検証
- Look-ahead Bias排除テストが含まれているか
- テナント隔離テストが含まれているか
- バックテストエンジン自体のテストが定義されているか

---

## 6. 確定済みUI方針

- **Figma更新**: オーナー側では行わない。開発側で調整
- **基本方針**: Figma画面を再現しつつ、仕様不整合は画面側を調整
- **トレーダー設定画面**: 2カラム・900px幅は踏襲。右ペインをタブ構造に再設計（基本情報/M1-M2/M3-M4/MX）
- **システム設定画面**: 2カラムメニュー構造を踏襲。セーフガード/コスト管理/経済指標を新規メニュー項目追加
- **ダッシュボード**: Figma再現。トレーダーパネルにパイプライン状態をコンパクト追加
- **取引履歴**: Figma再現。行クリックで4段階判定詳細を展開
- **通知設定**: Figmaほぼそのまま。トリガー種別の選択肢追加
- **新規画面**（バックテスト/パイプラインログ/設定変更履歴）: Figmaテイストに合わせて新規設計
- **画面修正の実施時期**: 設計書完成後の実装フェーズ

## 7. 未確定事項（オーナー回答待ち）

- セーフガード40項目のUI配置（トレーダー設定内 / システム設定内 / 混合）
