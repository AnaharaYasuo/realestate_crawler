# Issue #1137 仕様書: クローラー異常、0件取得時エラーHTML保存、掲載終了検知の厳格化、およびハング抑止

## 1. 概要 (Overview)
直近のクローリング運用監視において発生した以下の不具合・課題を是正する。
1. **0件取得時のHTML保存**: クローラーが正常終了（exit code 0）したものの取得件数が0件だった場合、および中間一覧ページから0件しかパースできなかった場合に、エラーページ/該当ページのHTMLをローカルログおよびGCSに確実に保存・アップロードする。
2. **画面上の明示的掲載終了文言の検知厳格化**: 物件スペックが存在しないことのみをもって掲載終了扱い（ListingEndedException）とすることを禁止し、必ず画面上に明示的な掲載終了文言（例:「掲載を終了しました」「お探しの物件は見つかりませんでした」等）が存在する場合のみ掲載終了として扱う。パナソニック（リアリエ）および全パーサーを対象とする。
3. **積水ハウス (sekisui) 0件取得修正**: 詳細ページURLの末尾スラッシュ変更（`/detail/[A-Za-z0-9]+`）に対応し、正規表現を修正する。
4. **ミサワホーム (misawa) メンテナンス検知**: サイトがメンテナンス画面を返却した場合に ServerBusyException を発生させ、エラーHTMLを保存する。
5. **個別パースエラー修正**:
   - 東急 (tokyu_mansion): 投資用・その他（土地・建物）において、建物面積と土地面積が併記されている物件を区分マンションと誤認させないよう PropertyTypeDetector を是正。
   - 住友 (sumifu_investment_apartment): 底地権等の土地物件において築年月が空でもバリデーションエラーにならないよう、`SumifuInvestmentApartment.chikunengetsuStr` に `blank=True, default=""` を許可し、`/tochi/` かつ土地表記のURLを正しく土地として扱う。
   - 三井 (mitsui_mansion_list_func): 中間ページ取得時のページサイズ limit=1000 を limit=200 に調整しタイムアウトを抑制。
6. **Cloud Run Job タイムアウト ＆ プロセスハング抑止**: 子プロセスの無応答（進捗なし600秒）を検知した際の強制終了（terminate/kill）を確実に機能させ、3時間タイムアウトでの全体中断を防ぐ。

## 2. 変更仕様 (Detailed Specifications)

### 2.1 0件取得時のHTML保存
- `src/crawler/package/api/api.py`:
  - `_sync_save_error_html_by_url`: ローカルの `ERROR_PAGES_DIR` だけでなく、`logs/runs/<date>/error_pages/<job_key>/` にも保存するか、FailureReporterを通じて確実にGCSアップロード対象ディレクトリへ配置する。
  - 中間ページパースで `len(detail_url_list) == 0` の場合、`FailureReporter.record_job_failure(..., error_type="ZeroCountFailure", raw_html=...)` を呼び出す。
- `src/crawler/scripts/ops/run_all_crawlers.py`:
  - `ZeroCountFailure` 検出時に、もしエラーHTMLが保存されていれば `FailureReporter.record_job_failure` に raw_html を渡して GCS `runs/<date>/error_pages/<job_key>/` にアップロードする。

### 2.2 画面上の明示的掲載終了文言の検知厳格化
- `src/crawler/package/parser/rearieParser.py`:
  - 行324〜328の「スペックなし -> ListingEndedException」の安易な判定を撤去。
  - タイトルまたは本文に明示的キーワード（`掲載を終了しました`, `お探しの物件は見つかりませんでした`, `掲載終了物件`, `ご指定のページは見つかりませんでした`, `該当する物件がありません`, `お探しのページは見つかりませんでした`等）が含まれる場合、あるいは特定の掲載終了セレクタ（`.mod-message-end`等）が存在する場合のみ `ListingEndedException` を送出する。
- その他全パーサーの精査: スペック不在のみで `ListingEndedException` を送出している箇所がないか確認し、明示的文言チェックを必須化。

### 2.3 積水ハウス (sekisui) パーサー修正
- `src/crawler/package/parser/sekisuiParser.py`:
  - 正規表現 `r'/detail/[A-Za-z0-9]+/'` を `r'/detail/[A-Za-z0-9]+/?'` に変更。
- `config/selectors/sekisui.yaml`:
  - `property_links_xpath`: `//a[contains(@href, '/detail/')]/@href`

### 2.4 ミサワホーム (misawa) メンテナンス検知
- `src/crawler/package/parser/misawaParser.py`:
  - 「システムメンテナンス中」「現在システムメンテナンスを実施しております」を検知した場合に `ServerBusyException` を送出。

### 2.5 個別パースエラーの修正
- `src/crawler/package/classifier/property_type_detector.py`:
  - `_is_unit_mansion_indicator`: `土地面積` と `建物面積` の双方が存在する場合、または種別が「その他」「ビル」「一棟」の場合は区分マンションと判定しない。
- `src/crawler/package/models/sumifu.py`:
  - `SumifuInvestmentApartment.chikunengetsuStr`: `models.TextField(default="", blank=True)`
- `src/crawler/package/parser/mitsuiParser.py`:
  - `limit=1000` を `limit=200` に変更。

## 3. テスト計画 (TDD & Verification)
1. ユニットテスト:
   - `test_rearie_strict_listing_ended`: スペック不在のみでは `ListingEndedException` にならず、文言ありの場合にのみ `ListingEndedException` になることを検証。
   - `test_sekisui_parser`: 末尾スラッシュなしURL（`/detail/C20010064363`）が正しくパースされることを検証。
   - `test_misawa_maintenance`: メンテナンス画面HTMLで `ServerBusyException` が送出されることを検証。
   - `test_tokyu_detector`: 土地面積と建物面積がある物件が区分マンションにならないことを検証。
   - `test_sumifu_blank_chikunengetsu`: `SumifuInvestmentApartment` に空文字の築年月が保存可能であることを検証。
2. リグレッションテスト (`/regression-test`):
   - Snyk / pytest 全件合格。
