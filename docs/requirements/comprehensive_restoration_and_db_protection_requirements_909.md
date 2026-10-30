# 本番DBローカル保護機構・マイグレ完全整合化・欠損データ全件復旧 要件定義書 (Issue #909)

## 1. 概要
本要件定義は、ローカル開発環境から本番データベースへの直接変更操作を機構的に永久遮断し、過去からのマイグレーションファイルの完全整合性を復元し、交通等の欠損データを全件復旧し、ML評価パイプラインのコネクション切断バグを解消するための仕様を定義する。

## 2. 目的
1. **本番DBの物理的保護**: 運用者の過失やローカルコマンドの誤実行による本番DBへの直接マイグレーション・変更を原理的に防ぐハードガードを導入する。
2. **マイグレーション整合性の完全復旧**: `0001` から最新までのマイグレーションチェーン、Django モデル定義、および本番DBテーブル構造の三者不整合をゼロにする。
3. **データ欠損の全件復旧**: 古いクロールデータで未格納だった三井物件等の `traffic` カラムや、未定義だった戸建て間取り・築年月データを再取得・整合化して全件復旧する。
4. **ML評価パイプラインの安定化**: `targets.py` のイテレーション中コネクション切断（OperationalError 2006）を解消し、`SumifuMansion` / `TokyuMansion` を含む全モデル評価を正常完了させる。

## 3. 要件一覧
- **REQ-909-001 (Production Hard Guard)**: ローカル環境から本番DB（Cloud SQL等）に向けた `migrate` / DDL / 書き込みコマンドの実行をコードレベルで検知し、即座に例外（`ProductionDatabaseDirectModificationBlocked`）を送出してプロセスを強制終了すること。本番へのスキーマ変更は CI/CD の Production Gate パイプライン経由のみ許可する。
- **REQ-909-002 (Migration Chain Consistency)**: コミット漏れおよび過去の差分を解消し、Django の `makemigrations --check` および `showmigrations` で一切の不整合がないマイグレーションファイルを整備すること。
- **REQ-909-003 (Model & Schema Alignment)**: `AthomeKodate` / `MitsuiKodate` など、初期からフィールドが脱落していたモデル定義を整合化し、DB・パーサー・バリデータ間で一貫したデータ保持を実現すること。
- **REQ-909-004 (Data Restoration Batch)**: `traffic` 等の欠損レコードを特定し、安全な再パース・再取得を行ってDBを全件復旧すること。
- **REQ-909-005 (ML Pipeline Connection Fix)**: `iter_unprocessed_chunks` 内で QuerySet `.iterator()` 実行中にコネクションを切断しないよう、コネクション管理を安全化すること。

## 4. アクセプタンスクライテリア
- [ ] ローカル環境で本番DB指定時に `manage.py migrate` を実行すると例外が発生してブロックされること。
- [ ] `python manage.py makemigrations --check` で未反映差分がゼロであること。
- [ ] `PropertyDataValidator` が `AthomeKodate` や `MitsuiKodate` を誤って全件欠損扱いしないこと。
- [ ] `SumifuMansion` / `TokyuMansion` の ML評価バッチが OperationalError 2006 を出さず完了すること。
- [ ] 全ユニットテスト・回帰テストが PASS すること。
