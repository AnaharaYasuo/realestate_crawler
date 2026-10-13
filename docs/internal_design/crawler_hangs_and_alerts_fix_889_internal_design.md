# 内部設計: クローラーハング誤検知防止および包括的パース不整合自動修復 (Issue #889)

## 1. 変更アーキテクチャ

### 1.1 `src/crawler/package/utils/crawler_watchdog.py`
* `INITIAL_DISCOVERY_GRACE_SEC` 定数を追加（デフォルト: 1800.0秒、環境変数 `CRAWLER_INITIAL_GRACE_SEC` で上書き可能）。
* `check_job_hung(last_activity_time, current_time=None, threshold_sec=HANG_THRESHOLD_SEC, prev_db_cnt=0, start_time=None)` に拡張。
* `prev_db_cnt == 0` かつ `start_time is not None` の場合、有効タイムアウト閾値を `max(threshold_sec, INITIAL_DISCOVERY_GRACE_SEC)` として計算。

### 1.2 `src/crawler/scripts/ops/run_all_crawlers.py`
* ハング検知ループ内で `active_processes` の `prev_db_cnt` と `start_t` を `check_job_hung` に引き渡すよう更新。

### 1.3 `src/crawler/package/parser/baseParser.py`
* `_is_non_property_href` の `skip_tokens` に `'/support/'`, `'/mikata/'`, `'/guide/'`, `'/manual/'`, `'/column/'` を追加。

### 1.4 `src/crawler/package/parser/mitsuiParser.py`
* `_parsePropertyDetailPage`: `item.traffic = traffic_str` を代入。
* `_parseTrafficLines`: `_getValueByLabel` で取得できない場合、`_get_specs(response)` の「交通」「最寄り駅」「沿線・駅」から行分割フォールバック。
* `MitsuiKodateParser._parsePropertyDetailPage`: `item.madori = self.get_madori(response) or self._parseMadori(response)` を代入。
* `MitsuiKodateParser._parseSetudouDetails`: `re.search(r'(?:幅員[：:]?\s*)?(?:約\s*)?(\d+(?:\.\d+)?)\s*[mｍ]', value)` に強化。
* `MitsuiMansionParser._parseKaisuStr`: `所在階 / 階建` 等のキー探索および `_getValueByLabel` ラベル検索フォールバックを追加。

### 1.5 `src/crawler/package/parser/athomeParser.py`
* `AthomeKodateParser._parsePropertyDetailPage`: `item.madori = self._parseMadori(response, specs) or self.get_madori(response)` を代入。
* `AthomeParser._parsePropertyDetailPage`: `item.chikunengetsuStr` に `完成時期`, `建築年月`, `建築時期` のフォールバックを追加。

### 1.6 `src/crawler/package/parser/afrParser.py`
* `_parsePropertyName`: H2/H1 から抽出できない場合、`<title>` タグの正規化テキストおよび `"旭化成ヘーベルハウス物件"` フォールバックを適用。
