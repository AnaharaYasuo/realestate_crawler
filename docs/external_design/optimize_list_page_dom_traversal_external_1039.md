# 外部設計書: 一覧ページ価格抽出のDOM走査最適化 (Issue #1039)

## 1. 外部インターフェース仕様
- `_extract_card_price(cls, link, context_cache=None) -> int | None`
  - 呼び出しシグネチャの完全な後方互換性を維持。
  - `_parsePageCore` のループ内でコンテキスト辞書 `context_cache` を保持・共有し、同一ページパース内で一度評価された親ノードの抽出価格を O(1) で即座に返却。

## 2. 影響範囲
- `src/crawler/package/parser/baseParser.py`: `_extract_card_price`, `_find_card_container`, `_parsePageCore`
- 既存の全パーサー（BaseParser 継承クラス）
