# Secret for Database Password
resource "google_secret_manager_secret" "db_password_secret" {
  secret_id = "realestate-db-password-${var.environment}"

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled_services]
}

resource "google_secret_manager_secret_version" "db_password_version" {
  secret      = google_secret_manager_secret.db_password_secret.id
  secret_data = random_password.db_password.result
}

# Secret for Database Monitor User Password
resource "google_secret_manager_secret" "db_monitor_password_secret" {
  secret_id = "realestate-db-monitor-password-${var.environment}"

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled_services]
}

resource "google_secret_manager_secret_version" "db_monitor_password_version" {
  secret      = google_secret_manager_secret.db_monitor_password_secret.id
  secret_data = random_password.db_monitor_password.result
}

# Random Password for ProxySQL Admin Interface
resource "random_password" "proxysql_admin_password" {
  length  = 24
  special = false
}

# Secret for ProxySQL Admin Credentials
resource "google_secret_manager_secret" "proxysql_admin_password_secret" {
  secret_id = "realestate-proxysql-admin-password-${var.environment}"

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled_services]
}

resource "google_secret_manager_secret_version" "proxysql_admin_password_version" {
  secret      = google_secret_manager_secret.proxysql_admin_password_secret.id
  secret_data = random_password.proxysql_admin_password.result
}


# Secret for Slack Bot Token (Placeholder version initialized)
resource "google_secret_manager_secret" "slack_bot_token" {
  secret_id = "realestate-slack-bot-token-${var.environment}"

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled_services]
}

resource "google_secret_manager_secret_version" "slack_bot_token_version" {
  secret      = google_secret_manager_secret.slack_bot_token.id
  secret_data = "xoxb-placeholder-token"

  lifecycle {
    ignore_changes = [secret_data] # ユーザーが後から手動登録した本番トークンを上書きしない
  }
}

# Secret for Slack App Token (Placeholder version initialized)
resource "google_secret_manager_secret" "slack_app_token" {
  secret_id = "realestate-slack-app-token-${var.environment}"

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled_services]
}

resource "google_secret_manager_secret_version" "slack_app_token_version" {
  secret      = google_secret_manager_secret.slack_app_token.id
  secret_data = "xapp-placeholder-token"

  lifecycle {
    ignore_changes = [secret_data] # ユーザーが後から手動登録した本番トークンを上書きしない
  }
}

# Secret for Estimation API Key (価格推定API外部呼出し用認証キー)
resource "google_secret_manager_secret" "estimation_api_key_secret" {
  secret_id = "realestate-estimation-api-key-${var.environment}"

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled_services]
}

resource "random_password" "estimation_api_key" {
  length  = 32
  special = false
}

resource "google_secret_manager_secret_version" "estimation_api_key_version" {
  secret      = google_secret_manager_secret.estimation_api_key_secret.id
  secret_data = random_password.estimation_api_key.result

  lifecycle {
    ignore_changes = [secret_data] # ユーザーが手動変更した場合も上書きしない
  }
}

import {
  id = "projects/sumifu/secrets/realestate-estimation-api-key-prod"
  to = google_secret_manager_secret.estimation_api_key_secret
}

import {
  id = "projects/sumifu/secrets/realestate-estimation-api-key-prod/versions/1"
  to = google_secret_manager_secret_version.estimation_api_key_version
}

