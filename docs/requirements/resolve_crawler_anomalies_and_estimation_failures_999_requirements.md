# 要件定義書: クローラー異常・価格推定失敗・パーサー異常解消 (Issue #999)

## 1. 背景・目的
Slack アラートで検知された以下の重大インシデントおよびパース異常を根本解決する。
1. `reguide - investment` クローラーのクラッシュ (Exit Code: 1)
2. バルク価格推定バッチにおける 4 モデル (`HomesTochi`, `HomesMansion`, `HomesInvestmentApartment`, `ReguideInvestment`) の評価失敗
3. 三井のリハウスにおける非物件URL (`/support/mikata/` 等) の混入および交通情報パース欠損
4. アットホームにおける一覧URL (`/list/`) の混入による物件名抽出失敗 (`Can not read property name`) および面積 0.0㎡ 欠損
5. 投資用アパートにおける一棟面積過小疑い（0.0㎡/1.0㎡）バリデーション異常

## 2. 要件一覧
### 要件 1: 非物件URLおよび一覧URLの完全排除 (URL Filtering & Base Guard)
- `baseParser._reject_non_property_url` において、`/support/`, `/mikata/`, `/guide/`, `/manual/`, `/column/`, `/list/` 等の非物件URLを確実に検出し、`SkipPropertyException` を送出して即時スキップすること。
- `athomeParser._is_athome_detail_path` において `/list/` および `/list$` で終わるパスを詳細URL判定から確実に除外すること。

### 要件 2: パーサーの抽出堅牢化 (Parser Robustness)
- `mitsuiParser`:
  - サポート・解説リンクを一覧収集から除外。
  - 交通文字列で複数路線が連結されているケースの分割と抽出の安定化。
- `athomeParser`:
  - 土地面積・建物面積で「敷地面積」「公簿面積」「実測面積」等の表記揺れを吸収し、0.0㎡ 欠損を防止。
- 投資アパート:
  - 建物面積/専有面積のフィールドマッピングを適正化し、0.0㎡ 判定や誤バリデーションアラートを抑制。

### 要件 3: バルク価格推定およびモデル評価の安定化 (ML Evaluation Resilience)
- `ReguideInvestment` および Homes 系モデル (`HomesTochi`, `HomesMansion`, `HomesInvestmentApartment`) のモデル種別解決・ディスパッチ不整合を修正し、評価バッチが落ちずに完走すること。

### 要件 4: 品質保証と回帰テスト
- 単体テスト (`test_crawler_anomalies_fix_999.py`) を作成し、全件パスを検証。
- 既存テストスイートを破壊しないこと。
