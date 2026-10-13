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

### 2.3 `restore_nomura_kodate_records(dry_run: bool = True) -> int`
- **処理ロジック**:
  - `NomuraKodate.objects.filter(madori='')` をイテレート。
  - `re.search(r'([1-9][0-9]?[SLKDKslkdk]+(?:\+[0-9]?[SLKDKslkdk]+)*)', f"{item.propertyName} {item.biko}")`
  - 一致した場合、`item.madori = match.group(1).upper()`。
  - `bulk_update(batch, ['madori'])` で一括 UPDATE。
