# クローラーおよびパーサー設計ポリシー (Crawler and Parser Policy)

## 1. 目的と存在理由 (Why)
データ収集の安定性確保、LLM コスト・レイテンシの最小化、およびデータ構造の統一を目的とします。

---

## 2. コア規範 (Rules & Boundaries)

### 2.1. 1物件1AIリクエスト原則 (Single Unified LLM Request Per Property)
- 物件に対して AI を利用する場合、小分けに複数回呼び出すことを厳禁とする。
- 1物件につき1リクエストで必要な全観点（種別判定、スペック、設備、画像等）を一括して構造化 JSON で抽出・判定させること。
- ルールベースで確定できる項目は極力そちらで処理すること。

### 2.2. 物件種別別 Base パーサー階層アーキテクチャ原則
- `src/crawler/package/parser/` 配下のパーサークラスは、`ParserBase` 直下の種別 Base パーサー（`MansionParserBase`, `KodateParserBase`, `TochiParserBase`, `InvestmentParserBase` 等）を必ず継承すること。
- 全抽象メソッド (`@abstractmethod`) を実装し、単体テストで 100% 準拠を検証すること。
- 関連スキル: [parser-implementation](../skills/parser-implementation/SKILL.md), [field-name-unifier](../skills/field-name-unifier/SKILL.md)

### 2.3. クローラー優先順位制御原則 (Smallest-Site-First)
- 処理が早く完了する小規模サイト・電鉄系・ハウスメーカー系から優先してクロールを実行し、大手ポータル（Homes, Athome）等は後回しにする。

### 2.4. 連続タイムアウト Fast-Fail ＆ サーキットブレイカー原則
- 相手サーバーが無応答・タイムアウトを繰り返す場合（連続3回以上）、即時中断（Abort）終了すること。

### 2.5. 0件取得のジョブ失敗分類原則
- クローリング処理が正常終了（Exit Code 0）した場合でも、新規取得件数が0件の場合は「0件取得失敗 (Zero-Count Failure)」としてアラート記録すること。

### 2.6. ML 評価の分離 ＆ バルク推論原則
- クローリング時は同期的 ML 評価を行わず、パースと DB 保存のみをミリ秒単位で完了させる。
- ML 評価はモデルを一括ロードして推論するバルク評価バッチで処理すること。
