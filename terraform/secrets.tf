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
