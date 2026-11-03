# 内部設計書 - 割安物件Slack通知のバス利用情報表記、統計マスタキャッシュ初期化、およびGEMINI_API_KEY配線 (Issue #1225)

## 1. 概要
- Issue #1225 に対応し、以下の3件の不具合・未反映設定を是正する。
  1. **アクセス表記におけるバス利用情報の欠落是正**: `_format_access_and_area` において、`busUse{i}`, `busWalkMinute{i}Str` (または `busWalkMinute{i}`), `busStation{i}` を考慮し、「中央線 三鷹 バス25分(停 中原三丁目) 徒歩1分」のような正確な交通情報を生成する。
  2. **AI定性評価における統計データ初期化と単位整合性**: `build_appraisal_context` 開始時に `_init_global_caches()` を呼び出し、`MunicipalPotential` の実データを参照可能とする。また `average_income` は千円単位で保存されているため、プロンプトテキスト整形時に適切に万円単位（`int(income / 10)`）に換算して表示する。
  3. **本番Cloud Run Job (`realestate-ml-pipeline-prod`) への `GEMINI_API_KEY` 配線**: Terraform において Secret Manager の `realestate-gemini-api-key-prod` を環境変数 `GEMINI_API_KEY` として注入する。

## 2. 変更対象コンポーネント
1. `src/crawler/scripts/ops/send_recommendations.py`:
   - `_format_access_and_area(prop)` のバス情報包含処理
2. `src/crawler/package/ml/appraisal_context.py`:
   - `build_appraisal_context(prop, ptype_jp)` 先頭での `_init_global_caches()` 実行
   - `format_appraisal_context_text(ctx)` の平均所得単位変換（千円 ➔ 万円）
3. `terraform/cloud_run_job.tf`:
   - `ml_pipeline_job` の `env` 定義に `GEMINI_API_KEY` を追加
4. `src/crawler/tests/unit/test_recommendation_rich_notification.py`:
   - バス利用を含むアクセス情報整形テストの追加
   - 統計キャッシュ初期化と平均所得表記のテスト追加
