# 内部設計書: Slackエラー読取・低件数検知のオートヒール統合およびathome/homesクローラー修復

## 1. モジュール構成・変更箇所

### 1.1 `src/crawler/scripts/debug_tools/auto_heal_parsers.py`
- 新設関数: `fetch_slack_error_targets(limit=100) -> list[dict]`
  - `aiohttp` または `urllib.request` を用いて、`SLACK_BOT_TOKEN` 経由で Slack チャンネル（`#alerts-*`, `#dev-agent`, `#property_alert`）から直近メッセージを取得。
  - 正規表現・キーワードマッチングにより、以下の障害を抽出：
    1. 0件取得警告: `対象サイト: (\w+)`, `種別: (\w+)`, `取得件数: 0`
    2. パース例外 / データ異常: `サイト: (\w+)`, `種別: (\w+)`, `エラー: (.+)`, `URL: (.+)`
    3. 低件数異常: 大規模サイト（athome, homes, mitsui, sumifu等）の取得件数が極小（< 5件）
  - 抽出結果を辞書形式で返却：
    ```python
    {
        "url": url,
        "company": company,
        "property_type": property_type,
        "reason": f"Slack障害検知: {error_detail}",
        "detected_at": timestamp,
        "source": "slack"
    }
    ```
- `scan_anomalies_and_generate_instructions()` の改修:
  - DBから取得した `heal_targets` に `fetch_slack_error_targets()` の結果をマージ。
  - `aggregate_and_sort_targets()` により一元的に頻度順 Top-50 を選定。

### 1.2 `.agents/skills/auto-healing/SKILL.md`
- スキル定義・手順の更新:
  - 「無差別探索・全チャンネル巡回の完全禁止」の記述を改訂。
  - 「Slackアラート・エラー集計の自動インジェスト（Step 1）」を明記。
  - 0件警告および極小件数異常をオートヒールの第一級対象として規定。

### 1.3 `athome` クローラー & パーサー
- `src/crawler/package/crawler/athome.py` / `src/crawler/package/parser/athome_*.py`:
  - 物件一覧URL抽出ロジックで最新のHTMLセレクター（`.object-list`, `a[href*="/mansion/"]`, `a[href*="/kodate/"]` 等）に対応。
  - フォールバック機構の追加。

### 1.4 `homes` クローラー & パーサー
- `src/crawler/package/crawler/homes.py` / `src/crawler/package/parser/homes_*.py`:
  - `priceStr` パース時の NoneType ガード（`re.search` が None を返した際の安全処理）。
  - 一覧カード抽出セレクターの更新。
