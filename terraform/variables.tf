variable "project_id" {
  type        = string
  description = "GCP Project ID"
  default     = "sumifu"
}

variable "region" {
  type        = string
  description = "Default GCP Region"
  default     = "asia-northeast1"
}

variable "zone" {
  type        = string
  description = "Default GCP Zone"
  default     = "asia-northeast1-a"
}

variable "environment" {
  type        = string
  description = "Environment name (e.g. prod, staging, dev)"
  default     = "prod"
}

variable "db_tier" {
  type        = string
  description = "Cloud SQL machine tier (e.g. db-f1-micro, db-g1-small, db-custom-2-7680)"
  default     = "db-f1-micro"
}

variable "db_name" {
  type        = string
  description = "Database name for MySQL"
  default     = "real_estate"
}

variable "db_user" {
  type        = string
  description = "MySQL user name"
  default     = "sumifu"
}

variable "crawler_cpu" {
  type        = string
  description = "CPU limit for Cloud Run Job (e.g. 2, 4)"
  default     = "2"
}

variable "crawler_memory" {
  type        = string
  description = "Memory limit for Cloud Run Job (e.g. 4Gi, 8Gi)"
  default     = "4Gi"
}

variable "crawler_timeout" {
  type        = string
  description = "Per-task execution timeout for the crawler Cloud Run Job (default 9h: 32400s; Cloud Run Jobs max is 86400s, but capped at 32400s by the Safety-Net hung threshold 33000s and ml_pipeline_schedule_cron). Also passed as CLOUD_RUN_JOB_TIMEOUT_SEC"
  default     = "32400s"

  validation {
    condition     = can(regex("^[0-9]+s$", var.crawler_timeout)) && tonumber(trimsuffix(var.crawler_timeout, "s")) > 0 && tonumber(trimsuffix(var.crawler_timeout, "s")) <= 32400
    error_message = "crawler_timeout must be \"<seconds>s\" between 1s and 32400s. Raising it requires moving DEFAULT_HUNG_THRESHOLD_SEC (ensure_resources_stopped.py), ml_pipeline_schedule_cron and the Cloud SQL backup start_time together."
  }
}

variable "crawler_task_count" {
  type        = number
  description = "Total number of tasks for Cloud Run Job task array"
  default     = 8
}

variable "crawler_parallelism" {
  type        = number
  description = "Number of tasks executing simultaneously in Cloud Run Job"
  default     = 8
}

variable "schedule_cron" {
  type        = string
  description = "Cron schedule expression in UTC (0 16 * * * is JST 01:00)"
  default     = "0 16 * * *"
}

variable "ml_pipeline_schedule_cron" {
  type        = string
  description = "ML pipeline cron in UTC. Must start after schedule_cron + crawler_timeout (10 1 * * * is JST 10:10 next day; crawl ends 01:00 UTC)"
  default     = "10 1 * * *"
}

# Budget Alert Variables
variable "billing_account_id" {
  type        = string
  description = "GCP Billing Account ID (e.g. 012345-6789AB-CDEF01)"
  default     = ""
}

variable "monthly_budget_amount" {
  type        = number
  description = "Monthly target budget amount"
  default     = 10000
}

variable "budget_currency" {
  type        = string
  description = "Currency for monthly budget (e.g. JPY, USD)"
  default     = "JPY"
}

variable "alert_email" {
  type        = string
  description = "Email address for budget alerts"
  default     = "wearemusiclover@gmail.com"
}

# Cloud Tasks Queue Configuration
variable "crawler_queue_max_dispatches_per_second" {
  type        = number
  description = "Maximum task dispatches per second for crawler queue"
  default     = 5.0
}

variable "crawler_queue_max_concurrent_dispatches" {
  type        = number
  description = "Maximum concurrent task dispatches for crawler queue"
  default     = 10
}

# ProxySQL Connection Pooling Variables
variable "proxysql_machine_type" {
  type        = string
  description = "Machine type for ProxySQL MIG instances"
  default     = "e2-micro"
}

variable "proxysql_min_replicas" {
  type        = number
  description = "Minimum instance count for ProxySQL autoscaler (0 for on-demand cost optimization at idle)"
  default     = 0
}

variable "proxysql_max_replicas" {
  type        = number
  description = "Maximum instance count for ProxySQL autoscaler (high load capacity limit)"
  default     = 2
}

variable "proxysql_backend_max_connections" {
  type        = number
  description = "Maximum database connections per ProxySQL instance to maintain backend database capacity saturation without overloading (Cloud SQL limit guard)"
  default     = 50
}

variable "new_relic_log_ingest_url" {
  type        = string
  description = "New Relic GCP Log Streaming ingest endpoint URL (e.g. https://log-api.newrelic.com/log/v1?Api-Key=...)"
  default     = ""
  sensitive   = true
}

variable "github_actions_sa_email" {
  type        = string
  description = "GitHub Actions deploy service account email (needs logging.configWriter for New Relic log sinks)"
  default     = "github-actions-crawler@sumifu.iam.gserviceaccount.com"
}


