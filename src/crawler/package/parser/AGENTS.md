# パーサー設計・実装ルール (src/crawler/package/parser/AGENTS.md)

本ディレクトリ（`src/crawler/package/parser/`）配下のパーサーを実装・改修する際は、以下の不変条件を厳守すること。

## 1. 種別別 Base パーサー継承と抽象強制（Abstract Enforcement）
- 全てのサイト別パーサーは、`MansionParserBase` / `KodateParserBase` / `TochiParserBase` / `InvestmentParserBase`（または `InvestmentParser`）を継承し、全 `@abstractmethod` を実装すること。
- 中間基底クラス（`InvestmentParser` 等）において、未実装の `@abstractmethod` を `return super()._parseXxx(...)` でダミーオーバーライドして抽象強制をバイパスすることを厳禁とする。

## 2. 1項目1メソッド原則 ＆ 標準コンバータ利用義務
- **1項目1メソッド**: 各フィールド抽出は `get_<field>(self, response)`（または `_parse_<field>`）に分離し、`parsePropertyDetailPage` 内に抽出ロジックをベタ書きしないこと。
- **独自価格パーサーの再実装禁止**: 価格抽出は必ず共通関数 `converter.parse_price()`（または `converter.parse_yen()`）を使用すること。`re.sub(r'\D', '', ...)` 等による独自価格計算（小数点「1.5億円→15億円」の10倍バグ原因）を厳禁とする。
- **禁止構文**: `importlib.reload(sys)` 等のレガシーハックの使用を禁止する。

## 3. 物件種別誤判定廃絶の4層防衛（Zero Property-Type Misclassification）
[`property_type_detector.py`](../utils/property_type_detector.py) および [`baseParser.py`](baseParser.py) の `_maybe_switch_parser` において以下の4層防衛を維持すること：
1. **Layer 1 (DOM ノイズ除去)**: `<header>`, `<nav>`, `<footer>`, `<aside>`, パンくず・サイドバー・おすすめ物件枠を除去したメインコンテンツ領域のみをテキスト判定に渡すこと。
2. **Layer 2 (物理構造 × 収益状態の直交分離)**: URLパス（`/mansion/`, `/kodate/`, `/tochi/` 等）と表題を最優先し、「利回り表記がある区分マンション（オーナーチェンジ）」を一棟アパートに誤分類しないこと。また、オフィス・店舗・倉庫・工場等の非住宅商用ビル（`excluded`）を居住用一棟アパートに混入させないこと。
3. **Layer 3 (ラベル限定スペック判定)**: `specs.values()` 全体（備考・PR文含む）への無差別キーワード検索を禁止し、種別・構造・階数等の明示的ラベルキーのみを判定に使用すること。
4. **Layer 4 (Post-Parse 物理不変条件ゲート)**: パース完了後のモデルインスタンスに対し、物理的不変条件（土地なのに専有面積・階数がある、区分なのに土地面積のみ等）を検証すること。

## 4. 1物件1AIリクエスト原則
LLM（Gemini）による属性補完を行う場合は、必ず1物件につき1回の統合リクエスト（`single_unified_property_ai_extractor`）で完結させること。
