# 仕様変更書: クローラー自己修復・価格推定安定化・パーサー異常解消 (Issue #1255)

本ドキュメントは、クローラー自己修復リクエスト（`[AUTO_HEAL_REQ]`）、バルク価格推定失敗、およびクローラー異常終了（タイムアウト/0件取得）を包括的に解消するための仕様定義書である。

---

## 1. 変更要件概要

| No | 領域 | 対象モジュール | 課題・不具合事象 | 変更仕様 |
|:---|:---|:---|:---|:---|
| 1 | パーサー / ML | `reguideParser.py`<br>`appraisal_context.py` | RE-Guide物件で `traffic` はパースされているが個別駅フィールド (`station1`) が空になり、乗降客数がデフォルト（10,000人）に固定される。 | `_parsePropertyDetailPage` 内で `_populateTraffic(item, item.traffic)` を実行。さらに `appraisal_context.py` で `station1` 欠損時に `traffic` 文字列から駅名候補を抽出するフォールバック防衛を追加。 |
| 2 | パーサー / 検証 | `mitsuiParser.py`<br>`baseParser.py` | 三井のリハウスにおいて「掲載終了/成約済」物件（`FKJBFA06` 等）が空データ（0円/0㎡）として保存され、Slackアラートが発報される。また `.property-detail-infos` からの交通抽出漏れ。 | `_parsePropertyDetailPage` 冒頭で `_raise_if_listing_ended` を確実に評価し、`ListingEndedException` で早期終了・非公開化。`.property-detail-infos` からの交通情報抽出を強化。 |
| 3 | パーサー / 検証 | `athomeParser.py`<br>`data_validator.py` | アットホームの所在階表記揺れ（地下階・メゾネット）による `ERR_MISSING_FLOOR`、および `buy_other`（売その他）から非住宅・更地が混入し `面積異常 (0.0㎡)` が検知される。 | 地下階表記（地下1階/B1F等）の所在階抽出正規表現拡張。`buy_other` において建物面積が取れない非住宅・更地の除外ガード追加、および「敷地面積」「公簿面積」等の表記揺れ吸収。 |
| 4 | クローラー / WAF | `mizuho_bypass.py` | みずほ不動産販売の一覧取得時、WAF/リニューアルの影響で「重要なお知らせ・店舗情報」にリダイレクトされ 0 件終了する。 | Playwright バイパスにおいてお知らせページへの転送を検知した際のCookie再確立・トップページ経由ナビゲーションを強化。 |
| 5 | クローラー基盤 | `differential.py`<br>`api.py` | 野村等の差分クローリング時、DB接続エラー（ProxySQLタイムアウト/2002）が発生した際に「全件フルクロール」へフォールバックして数千件が滞留し、7200秒タイムアウトでクラッシュする。 | 原則1.1（DB未接続放置の厳禁）に基づき、DB不通時はサイレントに全件フェッチへフォールバックせず安全に中断/フェイルファストする。タイムアウト/終了時の未完了タスクの安全なキャンセル（グレースフルシャットダウン）。 |
| 6 | ML価格推定 | `runner.py` | レコード数の多い `SmtrcMansion` / `NomuraMansion` の評価中に DB 接続断が発生し、モデル全体が失敗として脱落する。 | チャンク処理ループにおける一時的切断（`OperationalError`）に対する指数バックオフ付きリトライ（最大3回）および定期的な `close_old_connections()` の実施。 |

---

## 2. インターフェース ＆ 振る舞い仕様

### 2.1 RE-Guide パーサー
- `ReguideInvestmentParser._parsePropertyDetailPage(item, response)`:
  - `item.traffic = self._parseTransport1(response, specs)` の直後に `self._populateTraffic(item, item.traffic)` を実行。
  - `item.station1`, `item.railway1`, `item.walkMinutes1` 等の各交通フィールドが正しく値を持つこと。

### 2.2 三井のリハウス パーサー
- `MitsuiMansionParser`, `MitsuiKodateParser`, `MitsuiTochiParser`, `MitsuiInvestmentApartmentParser`:
  - `_parsePropertyDetailPage` の冒頭で `self._raise_if_listing_ended(response, getattr(item, "pageUrl", ""))` を実行。
  - 掲載終了ページに対しては `ListingEndedException` を送出し、価格 0 円 / 面積 0 ㎡ での保存を完全に阻止する。

### 2.3 アットホーム パーサー ＆ バリデータ
- `athomeParser._ensure_mansion_located_floor`:
  - `地下\d+階`, `B\d+F`, `\d+階建の\d+階` 等の表記を正しく所在階として認識。
- `athomeParser._athome_fill_invest_areas`:
  - 土地面積・建物面積のスペックキー候補を拡充。
  - 建物面積が正の値として存在しない `buy_other` 物件は `SkipPropertyException` を送出。

### 2.4 差分クローラー (Differential Crawl)
- `_process_differential_chunk(chunk_items, model_class, now, ttl_days)`:
  - DB接続エラー（`OperationalError: 2002 / 9001` 等）を捕捉した場合、全件フェッチとしてフォールバックせず、明示的に `DatabaseConnectionError` または例外を再送出してプロセスを安全に停止させる。

### 2.5 ML バルク価格推定
- `evaluate_single_model`:
  - チャンク推論・保存処理で一時的な DB 切断エラーが発生した場合、`close_old_connections()` を呼んだ上で最大 3 回までリトライを行い、一時的瞬断によるモデル脱落を防ぐ。
