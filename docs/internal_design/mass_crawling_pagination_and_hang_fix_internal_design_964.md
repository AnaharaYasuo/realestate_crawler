# 内部設計書: 全クローラーのページネーション・上限キャップ・ハング根絶と大量クローリング対応

## 1. モジュール詳細設計

### 1.1 `MitsuiParser` / `mitsui.yaml`
- `config/selectors/mitsui.yaml`: `next_page` セレクターの検証と強化。
- `MitsuiParser.getPropertyListNextPageUrl`: 次ページURLが同一URLや無限ループにならないよう検証。

### 1.2 `SumifuParser` / `sumifu.yaml`
- `config/selectors/sumifu.yaml`: `next_page` セレクターの最新DOM適応。
- `SumifuParser.getPropertyListNextPageUrl`: JavaScriptリンク除外と相対パス解決の保証。

### 1.3 `TokyuParser` / `tokyu.yaml`
- マンションのスタートURLを広域一括から「都道府県・市区町村」単位への展開に変更し、100件上限を突破。

### 1.4 `NomuraParser` / `nomura.yaml`
- マンション・土地の `next_page` セレクター適応。

### 1.5 他サイト群（smtrc, athome, homes, seibu, heim, sotetsu, keisei, sumirin, sekisui等）
- 各パーサーの `getPropertyListNextPageUrl` および `parsePropertyListPage` の次ページリンク生成ロジックの修正。

## 2. 大量クローリング検証設計
- 単なる数件テストではなく、各クローラーにおいて複数ページ（最低20〜50ページ以上、数千件規模）の巡回・URL回収が途切れず進行することを検証する専用スクリプトを作成・実行する。
