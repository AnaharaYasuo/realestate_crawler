# 要件定義・内部設計書: 住友不動産投資用ビットマスク是正および相鉄エリア制限解除

## 1. 背景・課題
- **Issue**: [#1052](https://github.com/AnaharaYasuo/realestate_crawler/issues/1052)
- 住友不動産販売ステップPRO（`sumifu_investment`）において、検索URLの種別指定ビットマスク `smk` のビット位置指定がオフバイワンを起こしていた。
  - `invest_kodate`: `000000100000`（7桁目: 工場・倉庫 / 6件）が指定され、真の投資用戸建て（6桁目: `000001000000` / 153件）が取得できていなかった。
  - `invest_apartment`: `010000000000`（2桁目: ビル一棟 / 69件）が指定され、真のアパート一棟（3桁目: `001000000000` / 406件）が取得できていなかった。
- 相鉄不動産（`sotetsu`）において、開始URLに `a5[]=13209`（町田市のみ）がハードコードされており、神奈川県（横浜・大和・海老名等）の本拠地エリアが除外され、極少件数（2〜3件）にとどまっていた。

## 2. 仕様変更内容 (SDD)
### 2.1. 住友不動産投資用 (`package/api/sumifu_investment.py`)
- `ParseSumifuInvestKodateStartAsync.urlList`:
  - 変更前: `["https://www.stepon.co.jp/pro/ca_0_001/?smk=000000100000"]`
  - 変更後: `["https://www.stepon.co.jp/search/list/?type=pro2&searchType=area&smk=000001000000&ca=0_001"]`
- `ParseSumifuInvestApartmentStartAsync.urlList`:
  - 変更前: `["https://www.stepon.co.jp/pro/ca_0_001/?smk=010000000000"]`
  - 変更後: `["https://www.stepon.co.jp/search/list/?type=pro2&searchType=area&smk=001000000000&ca=0_001"]`

### 2.2. 相鉄不動産 (`routes/sotetsu_routes.py`)
- `sotetsu_mansion_start`:
  - `https://www.sotetsu-re.co.jp/buy/res/area/1?t[]=1&s=new&o=desc`
- `sotetsu_kodate_start`:
  - `https://www.sotetsu-re.co.jp/buy/res/area/1?t[]=2&t[]=3&s=new&o=desc`
- `sotetsu_tochi_start`:
  - `https://www.sotetsu-re.co.jp/buy/res/area/1?t[]=4&s=new&o=desc`
- 市区町村ID（`a5[]`）を除去し、全線・全エリアの流通物件を対象化。

## 3. テスト計画 (TDD)
1. 単体テスト:
   - `test_sumifu_investment_seed_urls`: `sumifu_investment.py` の開始URLおよび `smk` 値が正しく設定されていることをアサート。
   - `test_sotetsu_routes_urls`: `routes/sotetsu_routes.py` のURLに対象外の市区町村絞り込みパラメータ（`a5`）が含まれていないことをアサート。
