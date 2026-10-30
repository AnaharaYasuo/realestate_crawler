# 仕様書: Issue #1122 クローリング異常・パースエラー復旧およびHomes未評価レコードバルク推定

## 1. 概要
2026-10-26のクローリング実行およびMLバルク価格推定で発生した以下の異常・エラーを是正し、パイプラインの安定性とデータ整合性を確保する。
1. ML価格推定における Homes 未評価レコード（HomesMansion, HomesInvestmentApartment）の滞留解消（対応完了）。
2. `mitsui - tochi`: ページ本文の「小学校まで約11300m」等の周辺施設距離が接道幅員フォールバック正規表現に誤マッチし、DB桁数上限（`DecimalField(max_digits=4)`: 99.99m）を超過してバリデーションエラーになる問題の修正。
3. `nomura - investment_apartment / investment_kodate`: `currentStatus`（現況）がテーブルに記載されていない物件で空文字バリデーションエラー（`blank=False`）となる問題の修正。
4. `sumai1 - investment`: 満室時想定収入がなく現行収入（`genko_shunyu`, `genko_rimawari`）のみ記載の物件で `annualRent` 等が未設定となりバリデーションエラーになる問題、および投資用一覧から他種別（土地・戸建）URLを拾ってパース失敗する問題の修正。
5. `sumifu - investment_apartment / kodate / tochi`: 「築年月不詳」物件における `chikunengetsu` の `blank=False` エラー、および `chisei` や `kouzou` 等の任意項目が `blank=False` であることによるバリデーションエラーの修正。
6. `tokyu - kodate / tochi`: `TokyuKodate.saikou` の `blank=False` エラーの修正、および `sumikae.ttfuhan.co.jp`（東急住宅販売/Totate系）URLが誤って `tokyu` パーサーへルーティングされパース失敗する問題のルーティング修正。
7. `rearie - mansion`: 掲載終了物件のリダイレクト例外（`ListingEndedException`）が適切に拾われずエラーとして扱われていた問題の修正。

## 2. 機能要件
- 接道幅員フォールバック処理において、道路幅員として非現実的な値（50m超など）や周辺施設距離の誤マッチを確実に除外し、`max_digits=4`（99.99m）の範囲内のみを抽出すること。
- 各種モデルにおいて、Webサイト上で記載が省略され得る任意フィールド（`currentStatus`, `chisei`, `saikou`, `kouzou`、および築年月不詳時の `chikunengetsu`）に対して `blank=True` を設定し、Django `full_clean()` での不当な例外発生を防ぐこと。
- `sumai1` 投資用パーサーにおいて、満室時想定収入が未定義でも現行収入・利回りをフォールバックして正しく家賃・利回りフィールドを設定すること。また投資用クローラーが種別の異なる詳細URLを不適切にパース対象としないこと。
- `UrlRouter` において、`sumikae.ttfuhan.co.jp` を東急リバブル（tokyu）ではなく totate 用パーサーにルーティングすること。
