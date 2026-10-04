# MySQL 認証プラグイン移行内部設計書 (Issue #572)

## 1. 修正対象ファイルと変更差分仕様

### 1.1 `terraform/database.tf`
Cloud SQL インスタンス設定から非推奨フラグ `default_authentication_plugin` を削除する。

```diff
     database_flags {
       name  = "skip_show_database"
       value = "on"
     }
-    database_flags {
-      name  = "default_authentication_plugin"
-      value = "mysql_native_password"
-    }
   }
```

### 1.2 `terraform/proxysql.tf`
ProxySQL の `/etc/proxysql.cnf` 生成テンプレートにおけるバックエンド MySQL サーバー定義で `use_ssl=1` を指定する。

```diff
     mysql_servers =
     (
         {
             address="${google_sql_database_instance.mysql_instance.private_ip_address}"
             port=3306
             hostgroup=0
             max_connections=${var.proxysql_backend_max_connections}
             max_replication_lag=0
-            use_ssl=0
+            use_ssl=1
             weight=1
         }
     )
```

## 2. データベースユーザー更新クエリ仕様
Cloud SQL 上で以下の SQL を実行し、既存ユーザーのプラグインを更新する：
```sql
ALTER USER 'sumifu'@'%' IDENTIFIED WITH caching_sha2_password BY '<既存パスワード>';
ALTER USER 'monitor'@'%' IDENTIFIED WITH caching_sha2_password BY '<既存パスワード>';
FLUSH PRIVILEGES;
```

## 3. テスト仕様 (TDD)
- **テストファイル名**: `src/crawler/tests/unit/test_mysql_auth_plugin_migration_572.py`
- **検証項目**:
  1. `terraform/database.tf` 内に `default_authentication_plugin` フラグが残存していないこと（静的解析アサーション）。
  2. `terraform/proxysql.tf` 内の `mysql_servers` 定義において `use_ssl=1` が設定されていること（静的解析アサーション）。
  3. Python の DB コネクション設定（`mysqlclient` / `PyMySQL` 等）において、`caching_sha2_password` 互換の暗号化ライブラリ（`cryptography`）がインストールされていること。
