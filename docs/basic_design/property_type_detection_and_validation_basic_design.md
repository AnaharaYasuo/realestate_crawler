# 基本設計書: PropertyTypeDetector 誤判定防止およびデータ整合性検証最適化

## 1. 全体構造
本機能は、クローラーのパーサー切り替え判定エンジン（`PropertyTypeDetector`）および監視バッチ（`validate_data.py`）の動作仕様を最適化し、誤ルーティングの根絶と監視アラートの信頼性向上を実現する。

```mermaid
flowchart TD
    HTML[クローリング対象ページ] --> Det[PropertyTypeDetector]
    Det --> |1. 数値利回り / Yield Guard| AP[apartment]
    Det --> |2. URL明示パス判定 /mansion/, /kodate/, etc.| URL_HIT[URLパスによる種別特定]
    Det --> |3. タイトル / specs | SPEC_HIT[メタデータ判定]
    Det --> |4. 本文テキスト判定| BODY_HIT[本文キーワード判定]
    
    URL_HIT --> ParserSelect[パーサー選定 & パース実行]
    SPEC_HIT --> ParserSelect
    BODY_HIT --> ParserSelect
    
    ParserSelect --> DB[(データベース)]
    DB --> Val[validate_data.py 直近7日走査]
    Val --> |異常検知時のみ| Slack[Slack各アラートチャンネル]
```

## 2. モジュール別基本設計
### 2.1 PropertyTypeDetector
- **URL判定の昇格**:
  - `_detect_rule_based` において、`_detect_from_url(url)` を `html_text` 走査より前（Yield Guard / specs / title の後、本文全文検索の前）に配置する。
  - URL パスが `/mansion/`, `/kodate/`, `/tochi/`, `/apartment/`, `/invest/` などの明確なドメインパスを含む場合、フッターの「土地権利」などの単語に引っ張られずに正しく種別を維持する。
- **土地キーワードの精密化**:
  - 単独の「土地」が「土地権利」「土地面積」など表項目の一部として HTML 全文に高頻度で出現するため、全文検索で誤判定を引き起こす。
  - `TOCHI_KEYWORDS` では「売土地」「売り土地」「建築条件付土地」「売地」等の売買意図が明示的なキーワードを対象とし、単独語「土地」による誤爆を抑制する。

### 2.2 validate_data.py
- **直近データ走査（`VALIDATE_DATA_DAYS`）**:
  - デフォルト `VALIDATE_DATA_DAYS = 7`。
  - `item.inputDate >= since` または `item.updateDateTime >= since_dt` の条件でクエリをフィルタリング（`filter(inputDate__gte=since)`）。
  - 全件フルスキャンを行いたい場合のために、環境変数または引数で全件モード（`--all` または `VALIDATE_DATA_DAYS=0`）も許容する。

### 2.3 PropertyDataValidator (Issue #769)
- **低価格・低単価の過剰検知防止**:
  - `_is_low_price_allowed(item, ptype)` により、地目（山林、原野、農地等）や物件名・備考（資材置場、持分等）、種別（土地・投資用）を判定。
  - 該当物件の下限価格を1万円、下限単価を10円/㎡に緩和し、適正な安価物件の誤検知を防止。

### 2.4 Tokyu / Odakyu パーサー是正 (Issue #769)
- **Tokyu**:
  - `_parseGrossYield`: 利回り記載なし時に `None` を返却。
  - `check_tokyu_listing_ended`: 一覧ページへのリダイレクト（収益物件一覧等）を掲載終了として検知。
  - `TokyuInvestmentKodateParser`: 土地面積のない区分所有物件をスキップ。
- **Odakyu**:
  - `_invest_card_traffic` および `_apply_invest_card_field`: 一覧カードから「交通」を抽出し `_populateTraffic` を呼出。
