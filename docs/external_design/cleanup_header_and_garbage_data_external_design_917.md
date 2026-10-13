# 三井ヘッダー行ゴミ混入防止・UPDATE復旧および健美家・野村等主要カラム欠損データの恒久修復 外部設計書 (Issue #917)

## 1. 概要
本設計書は、既存レコードを一切削除せず「UPDATE」によりデータを復旧・正常化するバッチ仕様およびCLI仕様を定義する。

## 2. UPDATE 復旧ロジック仕様
1. **健美家 (Kenbiya 全モデル)**:
   - 抽出元: `pageUrl` の `/s/{pref}/{city}/` パターン
   - 都道府県マッピング: `tokyo` ➔ `東京都`
   - 市区町村マッピング: `setagaya-ku` ➔ `世田谷区`, `minato-ku` ➔ `港区` 等の全50市区町村テーブル
   - 更新先: `address1`, `address2`, `address`
   - 用語解説クリア: `propertyName`, `priceStr` 等に `'を表示'` が含まれる場合、空文字に更新。
2. **三井 (MitsuiMansion, MitsuiTochi)**:
   - 保持項目: `id`, `pageUrl`, `propertyName`, `inputDate`, `inputDateTime`, `updateDateTime` 等
   - クリア対象（ヘッダー文字列 ➔ 空文字/None）:
     - `priceStr='価格'` ➔ `priceStr=''`, `price=None`
     - `address='所在地'` ➔ `address=''`, `address1=''`, `address2=''`, `address3=''`
     - `madori='間取り'` ➔ `madori=''`
     - `senyuMensekiStr='専有面積'` ➔ `senyuMensekiStr=''`, `senyuMenseki=None`
     - その他（`hikiwatashi`, `genkyo`, `tochikenri`, `torihiki`, `biko`, `kaisuStr`, `balconyMensekiStr`, `soukosuStr`, `kanriKeitai`, `kanriKaisya`, `kanrihiStr`, `syuzenTsumitateStr`, `tyusyajo`, `sonotaHiyouStr`, `bunjoKaisya`, `sekouKaisya`）で値がラベル名と一致するものを空文字に更新。
3. **野村戸建て (NomuraKodate)**:
   - 対象: `madori=''` かつ `propertyName` または `biko` に間取り表記が存在するレコード
   - パターン: `r'([1-9][0-9]?[SLKDKslkdk]+(?:\+[0-9]?[SLKDKslkdk]+)*)'`
   - 更新先: `madori`（大文字正規化）

4. **対象物件URL直接詳細巡回・公開終了保存仕様 (Direct Detail Recrawl & Delist Persistence)**:
   - 目的: 対象物件のURLが既知である場合、一覧探索をバイパスして直接詳細ページを開く。
   - 公開中時: パーサーにより最新スペック（間取り等）をパースし、DBモデルレコードを更新し、`PropertyEvaluation.is_published=True` を担保。
   - 公開終了時（HTTP 404/410/掲載終了メッセージ）: `PropertyEvaluation` レコードの既存有無を問わず、`is_published=False`, `delisted_at=<検知日時>`, `property_id=<紐付けID>` を確実にDB保存。

## 3. バッチ CLI インターフェース仕様
```bash
# ドライラン（件数調査のみ、DB変更なし）
python src/crawler/scripts/maintenance/update_and_restore_garbage_records.py

# 実UPDATE実行（本番環境またはCI/CD環境のみ実行可能）
python src/crawler/scripts/maintenance/update_and_restore_garbage_records.py --execute

# 特定ターゲットのみUPDATE
python src/crawler/scripts/maintenance/update_and_restore_garbage_records.py --execute --target mitsui
python src/crawler/scripts/maintenance/update_and_restore_garbage_records.py --execute --target kenbiya
python src/crawler/scripts/maintenance/update_and_restore_garbage_records.py --execute --target nomura

# 直接詳細ページ巡回による最新化および公開終了反映（野村等）
python src/crawler/scripts/maintenance/update_and_restore_garbage_records.py --execute --target nomura --recrawl-detail --limit 50

# 汎用直接詳細再巡回（URL直接指定 または モデル・空フィールド指定）
python src/crawler/scripts/maintenance/recrawl_anomalies.py --urls "https://www.nomu.com/house/id/XXX/"
python src/crawler/scripts/maintenance/recrawl_anomalies.py --model NomuraKodate --field-empty madori --limit 100
```
