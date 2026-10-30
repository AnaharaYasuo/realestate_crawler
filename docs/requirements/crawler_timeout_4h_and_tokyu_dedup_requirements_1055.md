# 要件定義書: クローラー全体タイムアウト4時間化・東急無差別取得是正・DB負荷軽減 (Issue #1055)

## 1. 概要・背景
2026-10-21 未明のクローラー実行において、Cloud Run Job タスク2/3が10,495秒でタイムアウト強制停止され、緊急アラートが発報した。
調査の結果、以下の複合要因が判明した：
1. **パイプライン実行時間の上限不足**: 3時間（10,800秒）上限に対し、データ増加に伴いマージンが不足。4時間（14,400秒）への延長が必要。
2. **東急リバブルの物件リンク無差別取得による44,000件水増し**:
   - `baseParser.py` の `_parsePageCore` が HTML 内の全 `<a>` タグを無差別に走査していた。
   - 東急の物件カード内には同一物件の詳細URLを持つ `<a>` タグが14〜24個存在し、18物件のページで298リンクが抽出され、本来1,000〜2,000件の土地物件が44,505件に膨張。
   - 都道府県選択画面（全国）でもPC/SP等のナビゲーションから同一都道府県リンクが2重取得されていた。
3. **不要なDBフルテーブルスキャン `COUNT(*)` SELECT**:
   - 親プロセスの進捗監視（Watchdog）が15秒おきに全モデルに対して `inputDateTime`/`updateDateTime` の `COUNT(*)` を発行。
   - インデックスが存在しないため、ProxySQLおよびCloud SQLにフルスキャン負荷を与え続けていた。
4. **無進捗ハング判定タイムアウトの長期化（600秒）**:
   - 10分間の無進捗判定はパイプラインの停滞を招くため、180秒（3分）に短縮し、迅速に切り離す。

---

## 2. 目的・ゴール
- パイプライン全体のタイムアウトを 14,400s（4時間）に延長し、余裕を持った完了を保証する。
- 東急リバブルのパーサーにおいて、正規コンテナ・代表リンクからの抽出とURL重複排除を徹底し、取得件数を実物件数に正常化する。
- 親プロセスの不要なDB `COUNT(*)` SELECT を撤廃し、DB/ProxySQL への負荷を根絶する。
- 無進捗タイムアウト（`HANG_THRESHOLD_SEC`）を 180秒（3分）に短縮し、障害時の迅速なパイプライン前進を実現する。

---

## 3. 機能要件
### 要件1: タイムアウト設定の多層的一括4時間（14,400s）化
- `terraform/variables.tf`: `crawler_timeout` default を `"14400s"`、validation 上限を `14400` とする。
- `src/crawler/scripts/ops/run_pipeline.py`: `DEFAULT_TIMEOUT_SEC = 14400.0` とする。
- `src/crawler/scripts/ops/run_all_crawlers.py`: `timeout_sec` のデフォルトを `14400` とする。
- `src/crawler/scripts/ensure_resources_stopped.py`: Safety-Net の `DEFAULT_HUNG_THRESHOLD_SEC = 15000.0`（14,400 + 600秒）とする。

### 要件2: 東急リバブルの物件リンク無差別取得廃止と重複排除
- `TokyuParser`（`mansion`, `kodate`, `tochi`）の `parsePropertyListPage`:
  - 1ページ内で同一URLを二重に yield しないよう `seen_urls = set()` による重複排除を徹底する。
  - 物件カード（`propertyCardContents`）または代表詳細リンクに絞り込んで抽出する。
- `parseRootPage`（都道府県選択）:
  - PC版リスト（`prefecturesListPc`）または正規のエリア選択コンテナ内のリンクのみを重複排除（`set()`）して抽出する。
- `parseAreaPage`（市区町村選択）:
  - 市区町村別物件一覧リンク（`/a\d+/`）のみを対象とし、`select-town` や他地域へのナビゲーションリンクを除外する。

### 要件3: 進捗監視での不要な DB `COUNT(*)` SELECT 撤廃
- `src/crawler/scripts/ops/run_all_crawlers.py`:
  - `update_watchdog_progress` にて `get_count_for_job` を介した15秒おきの DB クエリ発行を停止。
  - 子プロセスのポーリング監視を軽量化し、無駄なクエリ発行をなくす。

### 要件4: 無進捗ハング判定タイムアウトの180秒（3分）化
- `src/crawler/package/utils/crawler_watchdog.py`:
  - デフォルトの `CRAWLER_HANG_THRESHOLD_SEC` または既定値を `180.0` とする。
- `terraform/cloud_run_job.tf`:
  - `CRAWLER_HANG_THRESHOLD_SEC` 環境変数を `"180"` とする。

---

## 4. 非機能要件
- 既存テストコード（ユニットテスト）の整合性を維持し、全てパスすること。
- DB スキーマ変更（マイグレーション）を伴わないこと。
