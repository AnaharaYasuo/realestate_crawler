# Issue #1500 仕様書: SmtrcInvestment における kaisu カラム追加マイグレーション

## 1. 背景・目的
Issue #1443 (#1460) において `SmtrcInvestment` モデルへ `kaisu = models.IntegerField(null=True, blank=True)` が定義されたが、データベースマイグレーションファイルが生成・適用されていなかった。
このため、日次 ML パイプラインの Step 1/5 (`validate_data.py`) 実行時に以下のエラーが発生し、処理が停止していた：
```
OperationalError: (1054, "Unknown column 'smtrc_investment.kaisu' in 'field list'")
```

## 2. 変更仕様
1. **マイグレーションファイル `0074_add_smtrc_investment_kaisu.py` の追加**:
   - `smtrc_investment` テーブルに対して `kaisu` (INTEGER NULL) カラムを追加する。
   - 既存テーブルにカラムが存在しない場合のみ `ALTER TABLE` を発行する安全かつ冪等な `RunPython` 構成とする。
2. **データベーススキーマ仕様書の更新**:
   - `docs/internal_design/database_schema.md` の `SmtrcInvestment` 定義に `kaisu` (Int, NULL許容, 階数数値) を明記。
3. **回帰防止テストの追加**:
   - `src/crawler/tests/unit/test_migration_0074_smtrc_kaisu_1500.py` を追加し、モデル定義、マイグレーション依存関係、および DDL 発行ロジックを検証する。
