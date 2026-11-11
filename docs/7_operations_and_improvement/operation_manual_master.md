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

---

**最終更新**: 2026年11月11日  
**バージョン**: 1.2 (外部基礎データ定期更新スケジュール・GCS同期運用手順追記)

