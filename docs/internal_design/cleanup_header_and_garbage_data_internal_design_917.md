# 三井ヘッダー行ゴミ混入防止・UPDATE復旧および健美家・野村等主要カラム欠損データの恒久修復 内部設計書 (Issue #917)

## 1. モジュール構成
- 対象スクリプト: `src/crawler/scripts/maintenance/update_and_restore_garbage_records.py`
- 単体テスト:
  - `src/crawler/tests/unit/test_header_row_skip_guard_917.py`
  - `src/crawler/tests/unit/test_nomura_madori_fallback_917.py`
  - `src/crawler/tests/unit/test_update_and_restore_garbage_records_917.py`

## 2. 関数・クラス詳細仕様

### 2.1 `restore_kenbiya_records(dry_run: bool = True) -> int`
- **処理ロジック**:
  - `KENBIYA_TOKYO_CITIES` マッピング辞書（50市区町村スラッグ ➔ 日本語）
  - 各 Kenbiya モデルに対し、`address__icontains='を表示'` のレコードをイテレート。
  - `re.search(r'/s/([^/]+)/([^/]+)/', item.pageUrl)` により pref_slug, city_slug を抽出。
  - `pref_slug == 'tokyo'` の場合、`item.address1 = '東京都'`, `item.address2 = city_name`, `item.address = f"東京都{city_name}"`。
  - 用語解説文カラムをクリア（空文字/None）。
  - `bulk_update(batch, update_fields, batch_size=500)` で一括 UPDATE。

### 2.2 `restore_mitsui_records(dry_run: bool = True) -> int`
- **処理ロジック**:
  - `MitsuiMansion`, `MitsuiTochi` に対し、`priceStr='価格'` または `address='所在地'` のレコードをイテレート。
  - `priceStr = ''`, `price = None`
  - `address = ''` (住所が'所在地'の場合のみクリア)
  - `madori = ''` (間取りが'間取り'の場合のみクリア)
  - `senyuMensekiStr = ''`, `senyuMenseki = None`
  - その他ラベル名と一致する各カラムの文字列を空文字に更新。
  - `propertyName`, `pageUrl`, `inputDate` は保持。
  - `bulk_update` で一括 UPDATE。

### 2.3 `restore_nomura_kodate_records(dry_run: bool = True, recrawl_detail: bool = False, limit: int | None = None) -> dict[str, int]`
- **処理ロジック**:
  - `recrawl_detail=True` の場合: `recrawl_anomalies_async(model_name="NomuraKodate", field_empty="madori", limit=limit)` を呼び出し、直接詳細URLを開いてパース・更新または公開終了をDBへ保存。
  - `recrawl_detail=False` の場合: `NomuraKodate.objects.filter(madori='')` をイテレートし、物件名・備考から正規表現で間取りを補完 UPDATE。

### 2.4 `ParseDetailPageAsyncBase._handle_skipped_property` (直接巡回・公開終了保存)
- **処理ロジック**:
  - 詳細ページ取得時に `ListingEndedException` または `SkipPropertyException` を検知した際、`_handle_skipped_property()` が起動。
  - `PropertyEvaluation` レコードの存在確認（正規化URLおよび `UrlMatcher` 含む）。
  - **既存レコードが存在する場合**: `is_published=False`, `delisted_at=now_utc` に更新して保存。
  - **既存レコードが存在しない場合**: 対象パーサー/URLから会社名・種別を特定し、モデルテーブルの `pageUrl` と突合して `property_id` をリンクした上で、`PropertyEvaluation` レコードを新規作成して `is_published=False, delisted_at=now_utc` を確実に永続化。

### 2.5 `recrawl_anomalies.py` 汎用直接巡回拡張
- `TargetPropertyRef(property_url, property_id)`: 任意URLをタスク分割可能にする軽量参照型。
- `fetch_assigned_targets(urls=..., model_name=..., field_empty=...)`: URL直接指定またはモデル空カラム指定に対応。
- `_recrawl_single_url()`: `AnomalyDetailRunner` で直接詳細URLを開き、成否・公開終了を判定。
