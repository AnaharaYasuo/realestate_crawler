# 運用マニュアル (Operation Manual)

システム運用におけるトラブルシューティングおよびドキュメント管理のガイドラインです。

## 目次

1. [トラブルシューティング](#1-トラブルシューティング)
2. [ドキュメント管理](#2-ドキュメント管理)
3. [テスト実行手順](#3-テスト実行手順)
4. [外部基礎データ定期更新スケジュール ＆ 運用手順](#4-外部基礎データ定期更新スケジュール--運用手順)

---

## 1. トラブルシューティング

運用中に発生した問題の解決方法については、以下のドキュメントを参照してください。

- **[トラブルシューティングガイド](troubleshooting.md)**
  - 環境構築時のエラー（コンテナ起動失敗など）
  - クローラー実行時のエラー（保存失敗、タイムアウトなど）
  - データベース接続エラー
  - よくある質問 (FAQ)

## 2. ドキュメント管理

ドキュメントの追加・修正・削除に関するルールについては、以下のドキュメントを参照してください。

- **[ドキュメント管理ガイドライン](../1_architecture/documentation_guidelines.md)**
  - README.mdの更新ルール
  - ドキュメントの分類基準
  - サイト構造ドキュメントの扱い

## 3. テスト実行手順

- **全テスト実行（単体＋ライブ統合テスト）**:
  ```bash
  pytest src/crawler/tests/
  ```
- **ライブ統合テストのみ実行**:
  ```bash
  pytest src/crawler/tests/integration/test_live_reachability.py -v
  ```
- **オフライン単体テストのみ実行（ライブ統合テスト除外）**:
  ```bash
  pytest src/crawler/tests/ -m "not live"
  ```

## 4. 外部基礎データ定期更新スケジュール ＆ 運用手順

本システムが価格推定・DCF評価・投資判定で用いる全14種の外部公的データ・市場統計・空間キャッシュの詳細仕様は **[機械学習モデル仕様書 第4章](../4_valuation_and_ml/ml_model_specifications.md)** を正本（SSOT）とします。

### 4.1 本番自動定期実行スケジュール
Cloud Scheduler `realestate-ml-pipeline-daily-prod`（毎日 **05:10 JST**）が Cloud Run Job `realestate-ml-pipeline-prod`（[`run_ml_pipeline.py`](../../src/crawler/scripts/ops/run_ml_pipeline.py)）を起動し、データ種別ごとの更新周期（鮮度TTL）に応じて自動同期します：

- **毎日（05:10 JST）**:
  - マクロ経済指標（`MacroEconomicIndex`: 財務省10年国債金利CSV・当月マクロ指標の自動補完更新）
  - 賃料・期待利回りベンチマークの自社DB最新物件再集計（`RentMarketPotential` / `CapRateBenchmarkPotential`）
  - マンション建物マスタ更新（`BuildingMaster`）
  - 国土地理院（GSI）未解決町丁目の差分ジオコーディング、新規座標の 5m/10m 標高DEM微地形取得、掲載終了物件の成約スプレッド再集計、および **GCS `ml_reference_data/*.json` への自動アップロード**
- **毎週日曜（05:10 JST 週次バッチ）**:
  - 外部ポータル賃料メッシュのライブ収集（`--live-crawl-rent`）
  - **MLモデル4種別（`mansion`, `kodate`, `apartment`, `tochi`）および階層型OOFエンコーダ（`location_encoders.joblib`）の自動再学習と GCS `ml_models/` 更新**
- **月次・公表期連動（`--respect-ttl` による鮮度判定）**:
  - 国交省 L01地価公示・L02都道府県地価調査（公表月3・4・9・10月は14日TTL、通常月30日TTL）
  - 総務省 e-Stat 自治体統計、国土数値情報 S12 駅乗降客数・A29 用途地域・ハザードマップ・立地適正化計画・3年CAGR推移（30日TTL）
  - 社人研 2035年将来推計人口（90日TTL）

### 4.2 手動での全件強制リフレッシュ・バルク再評価コマンド
公表直後やローカル本番実行時に TTL を無視して全外部データを即時強制同期・再評価する場合は以下を実行します（有料AI課金ゼロ）：

```bash
# 1. 全外部基礎データ（全14種）の強制一括同期（GCSキャッシュ更新含む）
python src/crawler/scripts/sync_all_potentials.py --workers 8 --force

# 2. 全4種別MLモデル・階層OOFエンコーダの再学習
python src/crawler/package/ml/train.py

# 3. 全物件16並列・DB更新バッチサイズ100での一括価格再推定
python src/crawler/scripts/ops/run_bulk_ml_evaluation.py --force --no-skip-portals --workers 16 --batch-size 100
```

### 4.3 16並列バルク評価のロック競合防止 ＆ ハイブリッド画像解析レート制御（Issue #1380）
- **InnoDB 行ロックデッドロック・タイムアウト（1205）の構造的防止**:
  - [`persistence.py:bulk_update_evaluation_records`](../../src/crawler/package/ml/evaluation/persistence.py) は `PropertyEvaluation.objects.bulk_update` 実行前に必ず主キー（`pk`）昇順ソートを行い、ジッター付き指数バックオフ（最大5回試行）で一時的なロック競合を自動吸収します。
  - `PropertyEvaluation.analyzed_at` インデックスおよび重複照合候補プールのスレッド安全TTLキャッシュにより、16並列実行時のDB読み取り負荷を最小化します。
- **OpenCV × `gemini-2.5-flash` 低速レート制御**:
  - 画像・区画図解析は OpenCV によるローカル幾何・色相計測を先行実行し、`gemini-2.5-flash` 呼び出し時は `GEMINI_MIN_INTERVAL_SEC`（既定 `2.0` 秒間隔）および自動リトライ（`GEMINI_MAX_RETRIES`、既定 `4` 回）により無料・低速枠のレート制限超過を防止します。

---

## 5. GitHub Issue ドリブン自動修復パイプライン運用手順（Issue #1412）

日次パイプラインにおけるパーサー不整合の検知からコード修正・再クロールまでの自動連鎖は以下のスケジュールで稼働します：

| 時刻 (JST) | 実行基盤 | 処理内容 | トークン消費 |
| :--- | :--- | :--- | :--- |
| **05:10** | Cloud Run (`realestate-ml-pipeline-prod`) | データ整合性検証・`auto_heal_parsers.py` による GCS `auto_heal/latest_instruction.json` 更新 | Gemini Flash 要約のみ |
| **06:15** | GitHub Actions (`sync-auto-heal-issues.yml`) | [`sync_auto_heal_issues.py`](../../src/crawler/scripts/ops/sync_auto_heal_issues.py) により `auto-heal` ラベル付き Issue を自動起票・重複排除・解決時自動クローズ | **ゼロ** |
| **07:00** | Antigravity Scheduled Automation | `--list-actionable` で未解決 `auto-heal` Issue を確認し、対象あり時のみ Worktree でパーサー修正・テスト・PR作成・Auto-merge 設定 | **Antigravity 定額枠**（対象0件時は即終了） |
| **PRマージ後** | GitHub Actions (`auto-release-pr` ➔ `deploy-production`) | `production` 自動昇格・Cloud Run 更新・`realestate-recrawl-anomalies-pipeline-prod` 即時起動による異常データ再取得 | **ゼロ** |

### 手動運用コマンド
```bash
# アクション可能な auto-heal Issue 一覧の JSON 確認
python src/crawler/scripts/ops/sync_auto_heal_issues.py --list-actionable

# GCS 最新指示書からの Issue 同期ドライラン
python src/crawler/scripts/ops/sync_auto_heal_issues.py --pull-from-gcs --dry-run
```

---

## 6. 14日TTL経過物件の全件直接URLクロール＆掲載終了フラグ更新運用手順（Issue #1415）

一覧ページから消えた成約・取下げ物件の掲載終了フラグ（`PropertyEvaluation.is_published=False` / `delisted_at`）更新および 14日TTL経過物件の詳細スペック最新化は、**ローカル端末でのローカル本番実行（`AGENTS.md` 原則 1.1）**として毎日 **08:30 JST** に自動実行されます。

| 時刻 (JST) | 実行基盤 | 処理内容 |
| :--- | :--- | :--- |
| **毎日 08:30** | ローカル端末 (`EXECUTION_ENV=host` / Antigravity Background Schedule Sidecar `daily-ttl-expired-recrawl`) | [`run_ttl_expired_recrawl.py --ensure-local-prod-infra`](../../src/crawler/scripts/ops/run_ttl_expired_recrawl.py) を直接起動。`proxysql-instance-prod` 起動確認・`127.0.0.1:6033` IAPトンネル確立・`SELECT 1` 疎通検証の後、14日TTL経過物件を全件直接URLクロールし、掲載終了時は `is_published=False` 設定、継続時は通常物件保存＆`last_detail_fetched_at` 更新を実施 |

### 手動確認・実行コマンド（ローカル本番実行）
```bash
# 対象件数のドライラン確認（インフラ自動接続付き）
python src/crawler/scripts/ops/run_ttl_expired_recrawl.py --ensure-local-prod-infra --dry-run

# 件数上限を指定した動作確認実行
python src/crawler/scripts/ops/run_ttl_expired_recrawl.py --ensure-local-prod-infra --limit 20

# 日次本番フル実行（14日TTL経過物件全件）
python src/crawler/scripts/ops/run_ttl_expired_recrawl.py --ensure-local-prod-infra --ttl-days 14
```

---

**最終更新**: 2026年11月14日  
**バージョン**: 1.5 (Issue #1415: 物件詳細TTL 14日短縮とTTL経過物件の全件直接クロール・掲載終了フラグ更新手順追記)

