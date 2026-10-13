# 本番DBローカル保護機構・マイグレ完全整合化・欠損データ全件復旧 外部設計書 (Issue #909)

## 1. システム構成・インターフェース設計

### 1.1 本番DB保護ハードガード (ProductionProtectionGuard)
- **対象コマンド**: `manage.py migrate`, `manage.py sqlmigrate`, `manage.py dbshell`, `manage.py makemigrations`
- **判定条件**:
  - `DB_HOST` が本番環境（`host.docker.internal`, Cloud SQL IP, 3307ポート等）を指している。
  - かつ環境変数 `IS_PRODUCTION_DEPLOYMENT != "true"`（本番デプロイ専用トークン/フラグが存在しない）。
- **動作**:
  - `sys.exit(1)` または `RuntimeError("FATAL: Direct migration against production DB from local environment is blocked!")` を送出して処理を即時中断。

### 1.2 マイグレーション完全整合化
- **構成**:
  - `0062_sync_and_align_models.py`: 過去にDBへ直接入ってしまったテーブル（`crawled_adcast_*` 等）およびモデル定義の追加（`mitsui_investment_apartment.chikunengetsu` 等）を `SeparateDatabaseAndState` を用いて吸収。
  - DB上に既に存在するテーブル/カラムに対しては DDL をスキップしつつ、Django の内部 State を最新モデル定義と完全一致させる。
  - これにより、本番DBに対しても新規DBに対しても一切のエラーなく idempotent にマイグレーションが通過する。

### 1.3 ML評価パイプラインコネクション保護
- **対象**: `src/crawler/package/ml/evaluation/targets.py`
- **設計**:
  - `.iterator(chunk_size=...)` のイテレーションループ実行中に `close_old_connections()` を呼ばない。
  - チャンクの単位でプライマリキー（`id`）リストを取得し、各チャンクごとに個別の QuerySet でデータを処理してコネクションを安全に維持する。

### 1.4 バリデータ＆モデル整合性
- **対象**: `src/crawler/package/utils/data_validator.py`
- **設計**:
  - モデルに定義されていないフィールドに対しては、動的 `hasattr` または `model._meta.get_field` による存在確認を行い、定義自体がないモデルに対して「欠損」アラートを発報しないようセーフガードを配置。
