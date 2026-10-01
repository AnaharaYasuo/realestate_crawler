# MySQL 認証プラグイン移行要件定義書 (Issue #572)

## 1. 概要
MySQL 8.0 で非推奨化され、MySQL 8.4 LTS および 9.0 以降で削除・デフォルト無効化された認証プラグイン `mysql_native_password` から、推奨規格である `caching_sha2_password` への移行を行い、Cloud SQL ログに出力されている非推奨警告（スロットル通知）を恒久的に解消し、将来的なデータベース互換性を確保する。

## 2. 背景・課題
- **課題事象**: Cloud SQL (MySQL 8.0) ログに以下の非推奨警告スロットル通知が定期出力される。
  ```
  [Note] [MY-000000] [Server] Error log throttle is enabled. The mysql_native_password plugin deprecation warning while authentication will not be displayed for next 3600 secs. It will be suppressed.
  ```
- **原因**: 
  - `terraform/database.tf` において `default_authentication_plugin = "mysql_native_password"` が設定されていた。
  - Cloud SQL 上のユーザー（`sumifu`, `monitor`）が `mysql_native_password` を使用して認証していた。
- **将来リスク**: 
  - MySQL 8.4 LTS / 9.0 へのバージョン更新時に `mysql_native_password` が無効化・削除され、クローラーやバッチ、監視プロセスの接続不能障害を引き起こす。

## 3. 要件一覧
| 要件ID | 要件名 | 内容 | 優先度 |
|---|---|---|---|
| REQ-AUTH-001 | Cloud SQL デフォルト認証プラグインの正常化 | `terraform/database.tf` から非推奨フラグ `default_authentication_plugin = "mysql_native_password"` を削除し、MySQL 8.0 標準の `caching_sha2_password` に復元する。 | 高 |
| REQ-AUTH-002 | ProxySQL バックエンド接続の TLS 暗号化 | `terraform/proxysql.tf` の `mysql_servers` 定義において `use_ssl=1` を設定し、バックエンド接続を TLS 暗号化する（RSA 公開鍵交換不要で `caching_sha2_password` を高速かつ安全に疎通可能とする）。 | 高 |
| REQ-AUTH-003 | DB ユーザーの認証方式移行 | Cloud SQL 上のアプリケーションユーザー (`sumifu`) および監視ユーザー (`monitor`) の認証プラグインを `caching_sha2_password` に更新する。 | 高 |
| REQ-AUTH-004 | ゼロダウンタイム・既存接続互換性 | クライアント側（Cloud Run / Python）は `cryptography` (50.0.1) および `mysqlclient` (2.3.0) により既に完全対応しているため、アプリコードの改修なしで完全互換性を担保する。 | 高 |
| REQ-AUTH-005 | 自動テストによる回帰防止 | Terraform 設定ファイルおよび ProxySQL 定義の静的検証・テストを行い、リグレッションを防止する。 | 高 |

## 4. 受入基準 (Acceptance Criteria)
- [ ] `terraform/database.tf` に `default_authentication_plugin = "mysql_native_password"` が存在しないこと。
- [ ] `terraform/proxysql.tf` の `mysql_servers` において `use_ssl = 1` が設定されていること。
- [ ] テストコードにおいて、Cloud SQL / ProxySQL の設定値検証および接続互換性がアサーションされていること。
- [ ] ドキュメント階層（要件定義、基本設計、内部設計、README）が一貫して同期更新されていること。
