# 仕様書: Cloud Workflows 4タスク同期およびサイトメンテナンス耐性向上 (Issue #1148)

## 1. 概要
- クローリング全タスク集約レポートにて未実行ジョブが42件発生し、Task 0が3時間タイムアウト（Cloud Run Jobs上限）で脱落した問題の是正。
- 対象サイト（ミサワホーム、相鉄不動産など）の一時メンテナンス時（HTMLタイトル「システムメンテナンス中」「緊急メンテナンスのお知らせ」）に0件取得エラー（ZeroCountFailure）と誤判定されていた問題の是正。

## 2. 変更仕様

### 2.1 Cloud Workflows の taskCount 同期
- `terraform/workflows/daily_pipeline.yaml` において、`skipPortals` フラグ有効時の `effectiveTaskCount` を 3 から **4** に更新。
- Issue #1059 で導入された四大仲介（三井・住友・東急・野村）軸の 4 インスタンス決定論的分散構成と完全同期させ、三井不動産リアルティ等の超大規模サイトの負荷偏重による Task 0 の 3 時間タイムアウト脱落を解消。

### 2.2 サイト一時メンテナンス耐性の向上
- `src/crawler/package/parser/baseParser.py` に `SiteMaintenanceException`（`ServerBusyException` 継承）および `check_site_maintenance()` 判定関数を追加。
- 検出キーワード（`システムメンテナンス`, `ただいまメンテナンス`, `緊急メンテナンス`, `メンテナンス中`, `メンテナンスのお知らせ` 等）に一致するメンテナンス画面を即時検知。
- `ParseMiddlePageAsyncBase`（`api.py`）および `SotetsuParser`（`sotetsuParser.py`）の一覧・中間ページ取得処理でメンテナンス判定を実施。
- メンテナンス検知時は `SkipPropertyException`（`ServerBusyException`）として上位に伝播させ、エラーページ保存や障害アラートを抑止しつつ、安全にジョブを終了。
