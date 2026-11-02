# Issue #1188: New Relicダッシュボード 毎分瞬間CPU利用率(%)表示改修 仕様書

## 1. 概要と背景
New Relicダッシュボード（`RealEstate Full-Stack Unified Observability`）において、CPU消費状況の把握目的は「最適な並列数を探るためのボトルネック検証」である。
従来の `cpuUsageSeconds`（プロセスおよびcgroupの累積消費CPU秒数）は単調増加する累計値であり、並列スクレイピング中の瞬間的なCPU逼迫度や毎分のスパイクを把握できなかった。

本改修では、Row 10 のウィジェットを累計秒数から **毎分の瞬間的CPU利用率（%）**（`average(cpuPercent)`, `max(cpuPercent)`, `average(systemCpuPercent)`）および 1分バケット（`TIMESERIES 1 minute`）に改修し、コンテナ別のCPU負荷実態を直感的に可視化する。

---

## 2. 変更仕様

### 2.1 ダッシュボード定義の変更 (`src/crawler/scripts/setup_new_relic_dashboard.py`)

1. **Row 10 時系列グラフ**:
   - **タイトル**: `Container Minute CPU Usage % (Process & System)`
   - **クエリ (NRQL)**:
     ```sql
     SELECT average(cpuPercent) AS 'Process CPU % (毎分平均)', max(cpuPercent) AS 'Process CPU Peak % (瞬間ピーク)', average(systemCpuPercent) AS 'System Total CPU % (全体負荷)' FROM ContainerSample FACET containerName SINCE 24 hours ago TIMESERIES 1 minute
     ```

2. **Row 10 Sizing Summary テーブル**:
   - **クエリ (NRQL)**:
     ```sql
     SELECT max(memoryPercent) AS 'Max Mem %', average(memoryPercent) AS 'Avg Mem %', max(memoryUsageMb) AS 'Max Mem MB', average(memoryLimitMb) AS 'Limit MB', max(cpuPercent) AS 'Max CPU Peak %' FROM ContainerSample FACET containerName SINCE 7 days ago
     ```
     （※ `max(cpuUsageSeconds) AS 'Max CPU Sec'` を `max(cpuPercent) AS 'Max CPU Peak %'` に変更）

---

## 3. テストと検証方針
1. `src/crawler/tests/unit/test_new_relic_comprehensive_telemetry.py` 内のダッシュボード定義検証アサーションを更新し、`cpuPercent` の存在と変更後のタイトル・NRQLを検証。
2. `pytest` による単体テストの全件通過を確認。
3. アーキテクチャハーネスおよび静的解析（SonarCloud / CodeQL等）のパス。
