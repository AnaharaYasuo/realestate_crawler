# 仕様書: Cloud Run 4台分散・mtime進捗ウォッチドッグ・パーサー耐性・後続DB接続の総合改善

- **対象 Issue**: [#1059](https://github.com/AnaharaYasuo/realestate_crawler/issues/1059)
- **更新日**: 2026-10-21
- **ステータス**: 設計完了 / 実装中

---

## 1. 概要と背景
直近の本番実行ログ精査およびローカル本番実行により、以下の課題が特定された。
1. **Cloud Run Job 4台構成化の未反映**: 本来「四大仲介会社を各1台、件数が多い種別（マンション・戸建・土地）順に優先処理」とすべきところが 8 台設定のままであった。
2. **ウォッチドッグの進捗見失いによる誤殺**: 親プロセスの `COUNT(*)` フルテーブルスキャン抑止に伴い、ウォッチドッグが子プロセスの進捗を更新できず、初期猶予30分で四大仲介会社を一斉に `SIGKILL` していた。
3. **東急リバブルの投資用ページ混入**: 一般マンションクローラーに投資用URL（`/fudosan-toushi/`）が混入し、Strict Validation で異常終了していた。
4. **すまい1・リアリエのNullバリデーション落ち**: 特定項目（総戸数、道路幅、物件名等）の欠落により保存失敗・リトライ失敗していた。
5. **後続パイプライン（Step 5/6）におけるProxySQL接続タイムアウト**: 巨大テーブルに対する集計クエリがタイムアウト（10s）して切断されていた。

---

## 2. 外部設計・アーキテクチャ仕様

### 2.1. Cloud Run Job 4台分散 ＆ 四大仲介会社優先ソート
- **Terraform 設定**:
  - `terraform/variables.tf`: `crawler_task_count = 4`, `crawler_parallelism = 4` に設定。
- **タスク割り当て**:
  - 四大仲介会社 `BIG_4_COMPANIES = ["mitsui", "sumifu", "tokyu", "nomura"]`
  - `Task 0`: 三井のリハウス（`mitsui`）＋ 中小サイト群A
  - `Task 1`: 住友不動産ステップ（`sumifu`）＋ 中小サイト群B
  - `Task 2`: 東急リバブル（`tokyu`）＋ 中小サイト群C
  - `Task 3`: 野村の仲介＋（`nomura`）＋ 中小サイト群D
- **種別ソート優先順位**:
  - 各ホスト会社ジョブは **マンション ➔ 戸建 ➔ 土地 ➔ 投資用** の件数降順で先頭配置。
  - その後に各タスク担当の中小サイトジョブを配置。

### 2.2. ローカル進捗ファイル（mtime）方式によるウォッチドッグ監視
- **子プロセス側**:
  - 物件詳細の取得成功、差分キャッシュ更新、DB保存時にローカル軽量ファイル `logs/progress/progress_{company}_{ptype}.touch` を `touch`（`os.utime` による mtime 更新）。
  - DBアクセスを一切行わず、ナノ秒単位で最終活動時刻を記録。
- **親プロセス側（`crawler_watchdog.py`）**:
  - 各ジョブの進捗ファイルの mtime を監視。
  - `file_mtime > last_act` の場合に `last_act = file_mtime` を更新。
  - これにより、子プロセスが稼働中であれば 180 秒無進捗判定による誤殺が 100% 発生しない。

### 2.3. パーサー・バリデーション耐性
- **東急リバブル**:
  - `/fudosan-toushi/` を含むURLは、一般マンションパーサーで無理にパースせず `TokyuInvestmentApartmentParser` へ自動委譲（`PropertyTypeSwitch`）するか、適切にスキップ。
- **すまい1 / リアリエ**:
  - 総戸数・接道幅・物件名の欠落時に、デフォルト値フォールバックまたは警告付きで許容し、全体ジョブの異常終了を防止。

### 2.4. 後続パイプラインのDB接続耐性
- `send_recommendations.py` および `run_daily_prediction_diagnostics.py` において、ProxySQL 接続エラー（2013, 9001）発生時に `close_old_connections()` を呼んで自動再試行するラッパーを適用。
