# 11. セキュリティ設計書

## 1. 概要

認証・暗号化・鍵管理・プロンプトインジェクション対策を定義する。
本システムは私的利用が前提だが、マルチユーザー対応のDB構造を持つため、
テナント隔離を含むセキュリティ設計が必須。

---

## 2. 認証

### 2-1. 認証方式

```
初回リリース: JWT Bearer Token（簡易認証）
将来拡張: OAuth2.0 / 2FA（必要に応じて）

フロー:
  1. POST /api/v1/auth/login (email + password)
  2. サーバーがJWTを発行（access_token + refresh_token）
  3. access_token: 有効期限1時間
  4. refresh_token: 有効期限7日
  5. 全API呼出しにBearer Tokenを付与
```

### 2-2. パスワード管理

```
ハッシュ: bcrypt（cost factor=12）
ポリシー: 最低8文字、英数字混合（初回は簡易ルール）
```

---

## 3. 【監査1】マルチテナント隔離

```
3層防御:

Layer 1: TenantAwareSession（ORM層）
  - SQLAlchemy Sessionにuser_idを自動フィルタ
  - 全クエリに WHERE user_id = ? を自動付与
  → 07_database_schema.md で定義

Layer 2: @verify_ownership デコレータ（API層）
  - trader_idを受け取る全APIで所有権チェック
  - 不正アクセスは 403 Forbidden
  → 08_api_specification.md で定義

Layer 3: テスト（検証層）
  - テナント隔離テストで漏洩がないことを検証
  → 13_testing_strategy.md で定義
```

---

## 4. 【監査3】鍵管理

### 4-1. マスターキー

```
APIキー暗号化のマスターキーはDBに絶対に保存しない。

管理方法（優先順）:
  1. 環境変数: MASTER_ENCRYPTION_KEY
  2. ファイル参照: /etc/secrets/master_key（パーミッション600）
  3. 外部シークレット管理: AWS Secrets Manager / GCP Secret Manager

暗号化方式:
  - アルゴリズム: AES-256-GCM（認証付き暗号）
  - キー導出: マスターキーからHKDFで派生キーを生成
  - IV: 暗号化ごとにランダム生成（12バイト）
  - 暗号文と一緒にIV + 認証タグをDB保存
```

### 4-2. APIキー暗号化

```python
class KeyVault:
    """APIキーの暗号化・復号"""

    def __init__(self, master_key: bytes):
        self.master_key = master_key

    def encrypt(self, plaintext: str) -> bytes:
        """APIキーを暗号化"""
        iv = os.urandom(12)
        cipher = AES.new(self.master_key, AES.MODE_GCM, nonce=iv)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode())
        return iv + tag + ciphertext  # 12 + 16 + N bytes

    def decrypt(self, encrypted: bytes) -> str:
        """暗号化されたAPIキーを復号"""
        iv = encrypted[:12]
        tag = encrypted[12:28]
        ciphertext = encrypted[28:]
        cipher = AES.new(self.master_key, AES.MODE_GCM, nonce=iv)
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        return plaintext.decode()
```

### 4-3. ログマスキング

```
全ログ出力でAPIキー/シークレットをマスク:
  - api_key → "****" + 末尾4文字
  - api_secret → "********"
  - password → "********"
  - access_token → "Bearer ****..."
```

---

## 5. 【監査3】プロンプトインジェクション対策

```
二重防御:

入力側（Prompt Validator）:
  - ユーザー戦略テキスト（T-006）をサニタイズ
  - インジェクションパターン検出（正規表現マッチ）
  - 長さ制限（2000文字）
  - 制御文字除去
  → 05_ai_integration.md で詳細定義

出力側（Response Parser）:
  - AI応答のJSONスキーマバリデーション
  - enum値の範囲検証
  - 数値範囲の検証
  → 05_ai_integration.md で詳細定義
```

---

## 6. 通信セキュリティ

```
HTTPS:
  - 全APIエンドポイントはHTTPS強制
  - TLS 1.2以上

WebSocket:
  - WSS（WebSocket Secure）
  - 接続時にJWTで認証

取引所API通信:
  - HTTPS（取引所側の要件に準拠）
  - タイムスタンプベースのHMAC署名で中間者攻撃を防止
```

---

## 7. 環境変数一覧（セキュリティ関連）

```
MASTER_ENCRYPTION_KEY     ... APIキー暗号化マスターキー
JWT_SECRET_KEY            ... JWT署名キー
DATABASE_URL              ... DB接続文字列
TRADING_MODE              ... live / simulation / backtest
```

---

## 8. 関連設計書

- `05_ai_integration.md` - プロンプトインジェクション対策の実装
- `07_database_schema.md` - テナント隔離、暗号化カラム
- `08_api_specification.md` - 認証・認可
