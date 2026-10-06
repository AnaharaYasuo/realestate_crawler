# 基本設計: Safety-Net通知文言改善および住友不動産投資用戸建てセレクター修復

## 1. システム構成と変更概要
本改修では以下の2つのコンポーネントを修正する：
1. **インフラ安全停止監視スクリプト (`ensure_resources_stopped.py`)**:
   - ジョブ正常稼働時の Slack 通知メッセージ見出しを「クローラー/MLパイプライン正常実行中のためProxySQLの起動を継続しました」に改定。
2. **クローラーセレクター設定ファイル (`config/selectors/sumifu.yaml`)**:
   - `invest_kodate` および `invest_apartment` のセレクターブロックを追加し、既存の `investment` と同等のセレクター構造を適用。

## 2. インターフェース設計
### 2.1 Slack 通知メッセージ仕様
- **ヘッダー文言**:
  - 変更前: `:information_source: *【Safety-Net】クローラー/MLパイプライン正常実行中のためProxySQL停止をスキップしました*`
  - 変更後: `:information_source: *【Safety-Net】クローラー/MLパイプライン正常実行中のためProxySQLの起動を継続しました*`
- **本文フォーマット**:
  - プロジェクト、稼働ジョブ、ProxySQL インスタンス名/MIGサイズなどの稼働メトリクスは既存フォーマットを維持。

### 2.2 セレクター仕様 (`config/selectors/sumifu.yaml`)
- `invest_kodate` / `invest_apartment`:
  ```yaml
  invest_kodate:
    title: "h1.heading-1"
    price: "table.table-detail tr"
    address: "所在地"
    next_page: "次へ"
    property_links: "a[href*='/pro/detail_']"
    property_links_fallback: ".bukken-list .article-card a"
    region_xpath: '//a[contains(@href,"/pro/area_")]/@href'
    area_xpath: '//a[contains(@href,"/pro/area_") and contains(@href,"/list_")]/@href'
    property_list_xpath: '//div[@id="searchResultBlock" or @class="bukken-list"]//a[contains(@href, "/pro/detail_")]/@href'
    table:
      selector: "table.table-detail"
      header: "th"
      value: "td"

  invest_apartment:
    title: "h1.heading-1"
    price: "table.table-detail tr"
    address: "所在地"
    next_page: "次へ"
    property_links: "a[href*='/pro/detail_']"
    property_links_fallback: ".bukken-list .article-card a"
    region_xpath: '//a[contains(@href,"/pro/area_")]/@href'
    area_xpath: '//a[contains(@href,"/pro/area_") and contains(@href,"/list_")]/@href'
    property_list_xpath: '//div[@id="searchResultBlock" or @class="bukken-list"]//a[contains(@href, "/pro/detail_")]/@href'
    table:
      selector: "table.table-detail"
      header: "th"
      value: "td"
  ```
