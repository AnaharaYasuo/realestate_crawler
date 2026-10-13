# 三井ヘッダー行ゴミ混入防止・UPDATE復旧および健美家・野村等主要カラム欠損データの恒久修復 要件定義書 (Issue #917)

## 1. 概要
本要件定義は、全テーブル・主要カラムの欠損調査で判明したデータ不整合・欠損事象について、公開終了物件のレコードを一切削除（DELETE）せず、既存レコードのID・URL・物件名・登録日時を保持したまま「UPDATE（データ修復・正常化）」を行う要件を定義する：
1. 健美家（`kenbiya_*` 全種別 18,959件）: `pageUrl` のスラッグから都道府県・市区町村を解析し、`address`, `address1`, `address2` を正規住所に復旧・UPDATE。各カラムに残存する用語解説文（「〜を表示。」）をクリアして正常化。
2. 三井のリハウス（`mitsui_mansion`, `mitsui_tochi` 計6,198件）: 物件名やURLから地域情報を抽出しつつ、各カラムに入ってしまったラベル名文字列（`priceStr='価格'`, `madori='間取り'` 等）をクリア（空文字/None）に UPDATE。物件名・URL・登録日時は完全に維持。
3. 野村戸建て（`nomura_kodate` 454件）: 物件名や備考から間取りを正規表現抽出し、`madori` カラムを UPDATE 補完。
4. 通常クローリングにおけるヘッダー行誤登録の恒久防止（`_assert_not_header_row` ガード）。

## 2. 目的
1. **公開終了物件のデータ保持原則（Zero Record Deletion）**: 公開終了した物件はWebから再取得できないため、レコードの削除は一切行わず、既存レコードを基盤として健全なデータへと UPDATE 復旧する。
2. **データ整合性の完全担保**: DB内のダミー文字列（「〜を表示。」「価格」「間取り」等）や不正なゼロ値を正常化し、分析・価格推定への悪影響を排除する。
3. **本番運用の安全性（Zero Production Direct Mod）**: 本番DBに対する直接操作を遮断するハードガード（`assert_production_db_safety`）を維持しつつ、ドライランモードと実更新モード（`--execute`）を安全に提供する。

## 3. 要件一覧
- **REQ-917-001 (Universal & Mitsui Header Row Skip Guard)**:
  - `baseParser.py` および `mitsuiParser.py` において、`priceStr` がヘッダー文字列（`価格`, `販売価格` 等）または `address` がヘッダー文字列（`所在地`, `住所` 等）に完全一致する場合、即座に `SkipPropertyException` を送出してエンティティの保存を遮断すること。
- **REQ-917-002 (Kenbiya Address Recovery & Cleanup UPDATE)**:
  - 健美家全モデル（18,959件）について、`pageUrl`（例: `/s/tokyo/setagaya-ku/...`）から都道府県および市区町村を復元し、`address`, `address1`, `address2` を UPDATE すること。また、「〜を表示。」等の用語解説文を空文字/None に UPDATE すること。
- **REQ-917-003 (Mitsui Header Column Normalization UPDATE)**:
  - 三井（6,198件）の既存レコードについて、物件名・URL・登録日時を保持したまま、ラベル文字列（`priceStr='価格'`, `address='所在地'`, `madori='間取り'` 等）を空文字/None に UPDATE すること。
- **REQ-917-004 (Nomura Madori Fallback & Recovery UPDATE)**:
  - 野村戸建てのパーサーに物件名・備考からの間取りフォールバック抽出を実装し、過去データ（454件）に対しても抽出可能な間取りを `madori` カラムに UPDATE すること。
- **REQ-917-005 (Safety Guard & Dry-Run by Default)**:
  - バッチスクリプトはデフォルトでドライラン（件数集計のみ、DB変更なし）とし、`--execute` 付与時のみ `bulk_update` で実行すること。
- **REQ-917-006 (Direct Detail Recrawl & Delisted State Persistence)**:
  - 対象物件のURLが判明している場合、一覧クローリングを経由せず直接詳細ページを開くこと。その際、公開終了（HTTP 404/410または掲載終了メッセージ）が検知された場合は、`PropertyEvaluation` の既存レコード有無にかかわらず、`is_published=False` および `delisted_at`（検知日時）を確実にデータベースへ保存すること。公開中の場合は最新スペック（間取り等）をパースしてDBを更新・正常化すること。

## 4. アクセプタンスクライテリア
- [ ] 既存レコードの削除（DELETE）を行わず、全レコードを保持したまま UPDATE されること。
- [ ] 健美家の全レコードで `address1='東京都'`, `address2=<市区町村>`, `address='東京都<市区町村>'` に正しく復旧されること。
- [ ] 三井のヘッダー文字列（`priceStr='価格'`, `address='所在地'` 等）が空文字/Noneに更新され、物件名・URL・登録日時が保持されること。
- [ ] 野村戸建ての間取りが物件名・備考から抽出・補完されること。
- [ ] 対象物件URLの直接詳細巡回時、公開終了を検知した場合に `PropertyEvaluation` に `is_published=False` が確実にDB保存されること。
- [ ] 単体テストにおいて全てのガード・フォールバック・UPDATE処理が 100% 合格すること。
