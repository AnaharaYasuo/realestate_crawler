---
name: full-pipeline-execution
description: コンテナ起動確認から全件クローリング、MLモデル再学習、バルク価格推定、お宝物件リコメンド配信、パース異常・0件取得時のオートヒール＆リグレッションテストまでを一貫自動実行するエンドツーエンド（E2E）運用スキルです。
---

# Full Pipeline Execution Workflow

コンテナ動作確認からクローリング、ML学習・推論、リコメンド配信、自動復旧（Auto-Healing）までを全自動化する一貫ワークフローです。

---

## ワークフロー手順

### Phase 0: コンテナ起動確認 ＆ Pre-flight 疎通チェック
1. **コンテナ起動事実の検証 (Container Verification)**:
   - ホスト / Docker 環境双方でアプリコンテナが正常起動しているか確認。
   ```bash
   docker-compose ps
   docker-compose exec -T app python --version
   ```
   > [!IMPORTANT]
   > 単にログを見ずに `exec` コマンド等で実際の稼働事実を裏付けすること。
2. **Slack 疎通チェック (Step 0)**:
   - アラートおよびリコメンド通知先チャンネルの疎通確認。
   ```bash
   python -m src.crawler.scripts.debug_tools.check_slack_connection
   ```

---

### Phase 1: 一連のメインパイプライン実行
`run_pipeline.py` を呼び出し、以下の全工程を同期実行：
```bash
python -m src.crawler.scripts.ops.run_pipeline
```

#### パイプライン内包ステップ:
- **Step 1: 全件クローリング (`run_all_crawlers.py`)**:
  - Smallest-Site-First 原則（小規模・電鉄系優先）に基づきクローリング実行。
  - 連続3回タイムアウト時は Fast-Fail、新規取得0件時は「0件取得失敗 (Zero-Count Failure)」としてアラート記録。
- **Step 2: 不正データ検証 ＆ クレンジング (`validate_data.py`)**:
  - 重複・破綻データの検出とクレンジング。
- **Step 2.5: AI修復用バグ指示書生成 (`auto_heal_parsers.py`)**:
  - パース失敗・HTML構造変化ページの収集。
- **Step 3: 価格推定モデル学習 (`train.py`)**:
  - LightGBM / XGBoost / CatBoost / RandomForest の最新データ再学習。
- **Step 4: バルク価格推定・評価 (`run_bulk_ml_evaluation.py`)**:
  - 同期推論を行わず、1回でメモリロードして未評価物件を一括推論＆DB更新。
- **Step 5: お宝物件抽出 ＆ Slackリコメンド (`send_recommendations.py`)**:
  - 市場価格乖離・高利回り物件を抽出し指定Slackチャンネルに配信。

---

### Phase 2: オートヒール (Auto-Healing for Errors)
クローリングまたはデータ検証時にパース失敗や0件取得異常が記録された場合、自動的に修復スキルをトリガー：
- **/auto-heal スキルの呼び出し**:
  - `#alerts-*` チャンネルの投稿および `failed_slack_notifications.json` を分析。
  - 該当パーサー/セレクターの修正と単体検証。

---

### Phase 3: 品質・リグレッション総合検証 (Regression Testing)
パイプライン完了時、またはコード修復後は品質保証スキルを最終呼び出し：
- **/regression-test スキルの呼び出し**:
  1. **Snyk & SonarQube スキャン**: 脆弱性・型・重複コード検証。
  2. **動的生HTML 二段階検証**: 最新公開中物件で先頭3件 ➔ 追加17件（計20件/サイト×種別）スモーク検証。
  3. **純処理時間アサーション**: 静的パーサー 1,000ms 以内/件、Playwright 5,000ms 以内/件。
  4. **pytest 全件実行**: 単体テスト 100% SUCCESS を検証。
  5. **Slack 結果報告 & 表示自己チェック**: サマリー報告の送信結果を自ら取得・自己検証。
