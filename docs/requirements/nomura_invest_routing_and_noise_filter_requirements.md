# 要件定義書: 野村投資用戸建て誤ルーティング修復および非物件URLノイズ抑止

## 1. 背景・課題 (Issue #754)
- **課題1: 野村投資用戸建て（オーナーチェンジ戸建て）の誤判定・誤ルーティングおよびバリデーションエラー**:
  - 野村不動産ノムコムプロ（`nomu.com/pro/`）において、投資用戸建て（URL: `/pro/bukken_local_id/FB9C6017/` 等）のタイトルに「一戸建て」、パンくずカテゴリに「一戸建て（`/pro/house/`）」が含まれているにもかかわらず、投資シグナル（利回り等）のみによって一律 `apartment` と判定されていた。
  - さらに、`NomuraInvestmentApartment` モデルの `soukosu`（総戸数）フィールドに `blank=True` が設定されておらず、アパートパーサーでパースされた際に総戸数が `null` となり、Django モデルバリデーションで `ValidationError: Invalid fields: soukosu` が発生してクラッシュしていた。
  - `NomuraInvestmentKodate` モデルおよびパーサー（`NomuraInvestmentKodateParser`）が既に存在しているが、`UrlRouter` の `nomu.com/pro/` ルートに `invest_kodate` が登録されておらず、また `PropertyTypeDetector` の優先度でも戸建てシグナルが投資シグナル下で `invest_kodate` として解決されていなかった。
- **課題2: 非物件ノイズURLによる StrictExtractionFailed 警告多発**:
  - 東急リバブルの `/baikyaku/`（売却査定・相場検索ページ）等の非物件URLがクロール詳細キューに流入し、必須項目欠損による `StrictExtractionFailed` やバリデーションエラー警告がログに多発していた。

## 2. 要件一覧
- **REQ-754-01: 野村投資用戸建てモデルおよびパーサー連携の適正化**:
  - `NomuraInvestmentApartment.soukosu` に `blank=True` を付与し、アパートで総戸数未記載の場合や誤ルーティング時にも `null` を安全に受容可能とする。
  - `NomuraInvestmentKodate` に `madori`（間取り）フィールド（`blank=True, default=""`）を追加し、戸建て物件の間取り情報を保持可能とする。
  - `UrlRouter` に `nomu.com/pro/` の `invest_kodate` ルート（`NomuraInvestmentKodateParser` / `NomuraInvestmentKodate`）を登録する。
- **REQ-754-02: PropertyTypeDetector 投資物件サブ種別の的確な識別**:
  - `PropertyTypeDetector._match_keywords` および `_detect_rule_based` において、投資シグナル（利回り・オーナーチェンジ等）を検知した場合でも、タイトルやスペックに戸建てキーワード（「一戸建て」「戸建て」等）が含まれる場合は、一律 `apartment` ではなく `invest_kodate`（または `kodate`）として識別可能にする。
- **REQ-754-03: 非物件ノイズURL（`/baikyaku/`等）の早期除外強化**:
  - `ParserBase._is_non_property_href` および `_reject_non_property_url` に `/baikyaku/` を追加し、一覧巡回時および詳細取得前の両方で確実にスキップ（`SkipPropertyException`）させる。
