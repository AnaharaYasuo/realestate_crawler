# 東京セキスイハイム (`heim`) サイト構造・パーサー仕様

## 対象ドメイン・URL構造
- 分譲地ハブページ: `https://www.tokyo816.jp/bunjou/property/<property_id>/` または `.../index.html`
- 物件概要ページ: `https://www.tokyo816.jp/bunjou/property/<property_id>/outline/`
- 区画詳細ページ: `https://www.tokyo816.jp/bunjou/property/<property_id>/plan_detail/<plan_id>/`

## パース仕様（#1803 建ぺい率・容積率・交通補完）
- 分譲地ハブページ（`/bunjou/property/<id>/` および `/bunjou/property/<id>/index.html`）の HTML には物件概要テーブル（建ぺい率・容積率・詳細な交通表記）が含まれず、同階層の `outline/` ページ（`/bunjou/property/<id>/outline/`）に記載されている。
- `HeimParser.parsePropertyDetailPage` は、分譲地ハブページのパース後に `kenpei`・`youseki`・`traffic`・`railwayWalkMinute1` のいずれかが未抽出の場合、`outline/` URL を追加取得してスペック表（`th`/`td`, `dl`/`dt`/`dd`, JSON-LD `PropertyValue`）を抽出し、欠損項目のみを補完する。
- `outline/` 取得が失敗（ネットワークエラー・404等）した場合でも本体パース結果は破棄せず、警告ログのみ出力して継続する。
