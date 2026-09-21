# ==============================================================================
# GCP 予算アラート設定 (Cloud Billing Budget & Monitoring Alerts)
# ==============================================================================

# 1. メール通知チャンネルの作成 (Cloud Monitoring Notification Channel)
resource "google_monitoring_notification_channel" "budget_email" {
  count        = var.alert_email != "" ? 1 : 0
  display_name = "Real Estate Budget Alert Email (${var.alert_email})"
  type         = "email"

  labels = {
    email_address = var.alert_email
  }

  depends_on = [google_project_service.enabled_services]
}

# 2. Slack等への連携用 Pub/Sub トピック (予算通知イベント送信用)
resource "google_pubsub_topic" "budget_alert_topic" {
  # checkov:skip=CKV_GCP_83:Use default Google-managed encryption for budget alerts
  name = "budget-alert-topic-${var.environment}"

  depends_on = [google_project_service.enabled_services]
}

# 3. 予算アラートルール (Billing Budget)
# ※ billing_account_id が指定された場合に作成されます
resource "google_billing_budget" "budget_alert" {
  count           = var.billing_account_id != "" ? 1 : 0
  billing_account = var.billing_account_id
  display_name    = "Real Estate Crawler Monthly Budget (${var.environment})"

  budget_filter {
    projects               = ["projects/${var.project_id}"]
    credit_types_treatment = "INCLUDE_ALL_CREDITS"
  }

  amount {
    specified_amount {
      currency_code = var.budget_currency
      units         = tostring(var.monthly_budget_amount)
    }
  }

  # --- 段階的アラートしきい値設定 ---
  # 1. 予算の50%到達（定期巡航確認）
  threshold_rules {
    threshold_percent = 0.5
    spend_basis       = "CURRENT_SPEND"
  }

  # 2. 予算の80%到達（警戒アラート）
  threshold_rules {
    threshold_percent = 0.8
    spend_basis       = "CURRENT_SPEND"
  }

  # 3. 予算の100%到達（超過アラート）
  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "CURRENT_SPEND"
  }

  # 4. 予算の120%に達する予測（早期警戒・予測超過アラート）
  threshold_rules {
    threshold_percent = 1.2
    spend_basis       = "FORECASTED_SPEND"
  }

  all_updates_rule {
    monitoring_notification_channels = var.alert_email != "" ? [google_monitoring_notification_channel.budget_email[0].name] : []
    pubsub_topic                     = google_pubsub_topic.budget_alert_topic.id
    disable_default_iam_recipients   = false # Billing Account 管理者にも自動メール送信
  }

  depends_on = [
    google_project_service.enabled_services,
    google_monitoring_notification_channel.budget_email,
    google_pubsub_topic.budget_alert_topic
  ]
}
