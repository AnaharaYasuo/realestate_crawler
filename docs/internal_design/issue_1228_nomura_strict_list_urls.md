# 仕様書 (SDD): Issue #1228 野村不動産クローラーのURL取得対象厳格化

## 1. 背景と課題
野村不動産（`nomura`）のクローラー（mansion / kodate / tochi）において、以下の問題により過剰なタスク生成と2時間タイムアウトが発生していた。
1. **地域トップ（RegionPage）のノイズ混入**:
   - `https://www.nomu.com/mansion/area_tokyo/` などの都県トップから、おすすめ特集や他都県の市区町村リンク（神奈川・埼玉・千葉）が抽出されていた。
2. **一覧ページ（PropertyListPage）の広すぎるセレクタ**:
   - `a[href*='/mansion/id/']` により、ページ下部のおすすめ物件や関連リンクまで抽出され、同一物件が別ルートから多重ディスパッチされていた。
3. **未実行タスクの滞留**:
   - 重複したタスクがキューに大量に蓄積され、タイムアウト時に3,923件もの未実行タスクが破棄される原因となっていた。

## 2. 仕様変更内容

### 2.1 RegionPage（都県トップ）からの市区町村URL取得厳格化
- **対象セレクタ**: `.searchSelectTabFrame a`
- **フィルタリング条件**:
  - 現在巡回している都県の正規市区町村URL（`/(?:mansion|house|land)/area_{pref}/\d{5}/?$`）のみを抽出。
  - 広域エリア（例: `/area_tokyo/131/`）や他都県おすすめリンク（`.module_link_recommend` 等）を完全排除。

### 2.2 PropertyListPage（物件一覧ページ）からの物件URL取得厳格化
- **対象セレクタ**: `.item_title a[href*='/{ptype}/id/']`
- **効果**:
  - メインの一覧カードの見出しリンクのみを厳格に取得し、特集・おすすめ・閲覧履歴枠などのノイズを完全排除。
  - 同一一覧ページ内での重複URL排除（`seen` set）を確実に適用。

### 2.3 設定ファイル（YAML）の更新
- `config/selectors/nomura.yaml` の `property_links` および `region_links` を上記新仕様に合わせて統一・最適化。
