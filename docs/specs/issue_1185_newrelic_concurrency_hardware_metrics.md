# Issue #1185: New RelicにおけるCPU・ネットワーク消費量/消費率および最適並列度探索メトリクスの可視化 仕様書

## 1. 概要・背景
本システムでは、Cloud Run Jobs およびローカル環境において、多数の不動産サイトを並列（マルチプロセス・非同期）でクローリングしている。
最適な並列数（`parallel`、`playwright_parallel`、`detail_concurrency`）を探索・チューニングするためには、CPU使用率（プロセス・システム全体）、メモリ消費量/消費率、ネットワークトラフィック（送受信バイト数・秒間レート）、TCP接続数などのハードウェア・ネットワークリソースの推移と、その時の並列度および処理スループット（Items/sec）の相関を New Relic 上で一目で把握できるようにする必要がある。

## 2. 目的・要件
1. **リソースメトリクスの拡充 (`ContainerSample`)**:
   - 既存の CPU（`cpuPercent`, `systemCpuPercent`, `cpuUsageSeconds`, `loadAvg1m`）、メモリ（`memoryUsageMb`, `memoryLimitMb`, `memoryPercent`）、ネットワーク累積（`netBytesRecv`, `netBytesSent`）、TCP接続数（`tcpEstablishedCount`, `tcpTotalCount`）に加え、以下を自動算出・付与する：
     - `netRecvRateKbps`: 前回収集時からのデルタ受信速度（KB/秒）
     - `netSentRateKbps`: 前回収集時からのデルタ送信速度（KB/秒）
     - `parallel`: 実行時のジョブ並列度（環境変数 `CRAWLER_PARALLEL` または自動判定値）
     - `playwright_parallel`: 実行時のブラウザ並列度（環境変数 `CRAWLER_PLAYWRIGHT_PARALLEL` または自動判定値）
     - `detail_concurrency`: 実行時の詳細ページ並行度（環境変数 `DETAIL_CONCURRENCY` または `AdaptiveConcurrencyController` 計算値）
     - `active_jobs_count`: 実行時のアクティブジョブ数
2. **実行完了メトリクスの拡充 (`CrawlerExecution`)**:
   - `record_crawler_metrics` 呼び出し時に、実行時の並列度属性（`parallel`, `playwright_parallel`, `detail_concurrency`）を自動的に含め、並列度別の完了時間やスループット（`items_per_sec`）を NRQL で FACET 分析可能にする。
3. **New Relic 統合ダッシュボードの拡張 (`setup_new_relic_dashboard.py`)**:
   - ダッシュボードに「**並列度最適化・ハードウェア/NWリソース分析（Concurrency Tuning & Hardware Resources）**」セクションを追加：
     - 並列度別 CPU使用率・システムCPU使用率推移
     - ネットワーク送受信レート（KB/sec）推移
     - 並列度別 スループット（Items/sec）比較
     - 並列度・リソース飽和度（CPU・メモリ・TCP接続）サマリーテーブル
4. **NRQL 分析ガイド・クエリ集**:
   - ユーザーが New Relic Query Builder で最適な並列数を探索するための実践的 NRQL クエリ集を設計書に明記する。

## 3. 外部仕様・スキーマ変更
### 3.1 `ContainerSample` 追加属性
| 属性名 | 型 | 説明 |
|---|---|---|
| `netRecvRateKbps` | Float | 受信レート（KB/sec、前回計測からの増分 / 経過秒） |
| `netSentRateKbps` | Float | 送信レート（KB/sec、前回計測からの増分 / 経過秒） |
| `parallel` | Int | ジョブ並列度 |
| `playwright_parallel` | Int | Playwright並列度 |
| `detail_concurrency` | Int | 詳細ページ並行度 |
| `active_jobs_count` | Int | 同時実行中アクティブジョブ数 |

### 3.2 `CrawlerExecution` 追加属性
| 属性名 | 型 | 説明 |
|---|---|---|
| `parallel` | Int | 実行時ジョブ並列度 |
| `playwright_parallel` | Int | 実行時Playwright並列度 |
| `detail_concurrency` | Int | 実行時詳細ページ並行度 |

## 4. 影響範囲・リスク検証
- **影響範囲**: `newrelic_helper.py`, `run_all_crawlers.py`, `setup_new_relic_dashboard.py`, `docs/`
- **下位互換性**: 既存の属性名はすべて維持され、追加属性のみ付与されるため後方互換性は100%保たれる。
- **オーバーヘッド**: ネットワークのデルタ計算は `time.monotonic()` と前回のバイト数差分のみで計算され、オーバーヘッドはマイクロ秒オーダーで極小。
