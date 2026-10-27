# 要件定義書: Issue #1122

## 1. 目的
2026-10-26 クローリング実行レポートおよびエラーページ証拠（Evidence-First）に基づく、クローラー・パーサー・モデルの異常解消。

## 2. 要件項目
### REQ-1: 三井土地パーサー幅員抽出ガード
- 幅員として 50m を超える数値は周辺環境情報等の誤マッチと判定し除外する。
- 0m 以下、または 50m 超の場合は `roadWidth` に代入しない。

### REQ-2: 野村不動産投資用モデル・パーサーの現況（currentStatus）空文字許容
- `NomuraInvestmentApartment`, `NomuraInvestmentKodate` の `currentStatus` フィールドに `blank=True, default=""` を定義。
- パーサー側でも現況が存在しない場合に安全に空文字として処理する。

### REQ-3: すまいValue（sumai1）投資用パーサーの収入・利回りフォールバック
- `manshitsuji_sotei_shunyu` が空の場合、`genko_shunyu`（現行収入）および `genko_rimawari`（現行利回り）を採用する。
- 一覧ページでの URL 抽出において、他種別の詳細ページへの不要なクロール・パースを抑止する。

### REQ-4: 住友不動産（sumifu）モデルのバリデーション不整合解消
- `SumifuInvestmentApartment.chikunengetsu` に `blank=True` を定義（築年月不詳時は None を許容）。
- `SumifuKodate.chisei`, `SumifuTochi.chisei`, `SumifuInvestmentApartment.kouzou` に `blank=True` を定義。

### REQ-5: 東急リバブル（tokyu）モデルおよび UrlRouter の修正
- `TokyuKodate.saikou` に `blank=True` を定義。
- `sumikae.ttfuhan.co.jp` ドメインを `UrlRouter` で `tokyu` ではなく `totate`（戸建・土地）パーサーへ振り分ける。
