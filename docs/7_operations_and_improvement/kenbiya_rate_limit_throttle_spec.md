# 健美家 (Kenbiya) レートリミット対策・スロットリング制御仕様書 (Issue #1574)

## 1. 概要と背景
健美家（Kenbiya）クローラーは、物件リスト探索（約1.5万件超）後に詳細ページURLを並行ワーカープールへディスパッチして取得するアーキテクチャとなっている。
しかし、短時間に高頻度のリクエストが集中した際、健美家サーバー側から HTTP 429 (Too Many Requests) が返却され、パーサーのセーフガード（`ServerBusyException`）によりスキップされる事象が確認された。

本改修では、次回以降のクローリング実行においてサーバー負荷を低減し、HTTP 429 の発生を抑止して安定した物件取得を行うための恒久的なリクエストレート制御・並行度制御を導入する。

---

## 2. 変更仕様

### 2.1 API層におけるサイト別ダウンロードディレイの追加
- **対象**: `package.api.api.ParseDetailPageAsyncBase.SITE_DOWNLOAD_DELAYS`
- **仕様**: `kenbiya: 2.0`（秒）を登録。
- **効果**: 詳細ページフェッチ実行前に `_apply_download_delay_if_needed` が呼び出され、全並行ワーカー間で最低2秒の間隔（グローバルロック `_SITE_RATE_LOCK` により制御）が保証される。

### 2.2 パーサー層におけるスロットリング動作の常時有効化
- **対象**: `package.parser.kenbiyaParser.KenbiyaParserBase._throttle_before_request`
- **仕様**:
  - これまで `K_SERVICE` / `CLOUD_RUN_JOB` / `KENBIYA_THROTTLE=true` の環境のみで有効化されていたリクエスト間隔制御を、ローカル本番実行・全環境において**既定で有効化**する。
  - 最小インターバルは既定で `2.0` 秒とし、環境変数 `KENBIYA_MIN_INTERVAL` により柔軟にカスタマイズ（例: `3.0` 秒等）を可能にする。
  - 無効化したい場合は環境変数 `KENBIYA_THROTTLE_DISABLED=true` のみで明示的にスキップ可能とする。

### 2.3 動的並行度制御（Adaptive Concurrency）におけるキャップ設定
- **対象**: `package.api.adaptive_concurrency.AdaptiveConcurrencyController.SITE_CONCURRENCY_CAPS`
- **仕様**: `"kenbiya": 1` を追加。
- **効果**: 詳細並行度の上限をサイト単位で1並行に絞り込み、過剰なバーストアクセスを根底から防止する。

---

## 3. テストと検証方針 (TDD)
1. **単体テスト (`test_kenbiya_rate_limit_throttle.py`)**:
   - `ParseDetailPageAsyncBase.SITE_DOWNLOAD_DELAYS["kenbiya"]` が `2.0` 秒以上で定義されていることを検証。
   - `AdaptiveConcurrencyController.SITE_CONCURRENCY_CAPS["kenbiya"]` が `1` に設定されていることを検証。
   - `KenbiyaParserBase._throttle_before_request` がローカル環境下でも呼び出され、指定インターバル（`KENBIYA_MIN_INTERVAL`）を満たすスリープ制御が行われることをモック/実測テストで検証。
2. **既存テストおよびハーネス (`test_architecture_harness.py`)**:
   - リファクタリングおよび追加がプロジェクトアーキテクチャ規約に合致していることを検証。

## curl_cffi による TLS フィンガープリント模倣と直列実行 (Issue #1628)
- `kenbiyaParser.py` では `curl_cffi` (`AsyncSession(impersonate="chrome")`) を使用し、Chrome の TLS/HTTP2 フィンガープリントを模倣する。
- `KENBIYA_MIN_INTERVAL` のデフォルトを `1.0` 秒（+ `0.5〜1.5` 秒のランダムジッター）に設定する（Issue #1639, #1652）。
- `run_all_crawlers.py` で `kenbiya` 実行時は `parallel=1`（直列実行）を強制する。

## マルチイベントループ対応 (Issue #1646)
- `KenbiyaParserBase._request_lock` を `asyncio.Lock()` から `threading.Lock()` へ変更し、異なるイベントループから呼ばれた際の `RuntimeError: ... is bound to a different event loop` を防止する。

## 予防的60分クールダウンの既定無効化と差分クエリ時のProxySQL自動復旧 (Issue #1890)
- `src/crawler/package/api/kenbiya.py`: `KENBIYA_COOLDOWN_WORK_SECONDS` のデフォルトを `3600` から `0` に変更し、`COOLDOWN_WORK_SECONDS <= 0` の場合は `_KenbiyaDetailBase._get_cooldown_config()` が `None` を返すようにする。これにより、503 が発生していない安定稼働中に 60 分ごとに不要な 10 分停止を行わずスループットを維持する（実際の 503 検知時は `[Kenbiya503Recovery]` による自動 IP ローテーションが引き続き機能する）。
- `src/crawler/package/api/differential.py`: `_query_existing_records_sync` で `OperationalError` / `DatabaseError`（`2013`, `2006`, `2003`, `10061`, `lost connection`, `server has gone away`, `can't connect`）を検知した際、`_ensure_proxysql_tunnel_ready()` を呼び出して `proxysql-instance-prod` VM および IAP トンネルを自動復旧してからリトライする。
