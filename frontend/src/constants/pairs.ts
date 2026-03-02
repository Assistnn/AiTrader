/**
 * 通貨ペア定数 — Single Source of Truth (フロントエンド側)
 * バックエンド: backend/app/services/exchange/pair_normalizer.py と同期
 */

export const FX_PAIRS = [
  "USD_JPY", "EUR_JPY", "GBP_JPY", "AUD_JPY", "NZD_JPY",
  "CHF_JPY", "CAD_JPY", "EUR_USD", "GBP_USD", "AUD_USD", "NZD_USD",
] as const;

export const CRYPTO_PAIRS = [
  "BTC_JPY", "ETH_JPY", "XRP_JPY", "LTC_JPY", "BCH_JPY", "MONA_JPY",
] as const;

export type FxPair = typeof FX_PAIRS[number];
export type CryptoPair = typeof CRYPTO_PAIRS[number];
export type TradePair = FxPair | CryptoPair;

/** tradeType に応じたペアリストを返す */
export function getPairsForTradeType(tradeType: string): readonly string[] {
  return tradeType.toLowerCase() === "crypto" ? CRYPTO_PAIRS : FX_PAIRS;
}

/** ペア名を "USD_JPY" → "USD/JPY" の表示形式に変換 */
export function formatPairLabel(pair: string): string {
  return pair.replace("_", "/");
}

/** ペアの選択肢オブジェクト配列を返す */
export function getPairOptions(tradeType: string): { value: string; label: string }[] {
  return getPairsForTradeType(tradeType).map((p) => ({
    value: p,
    label: formatPairLabel(p),
  }));
}

/** 仮想通貨ペアかどうか判定 */
export function isCryptoPair(pair: string): boolean {
  return (CRYPTO_PAIRS as readonly string[]).includes(pair);
}
