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
  description = "Execution timeout for Cloud Run Job (up to 1h: 3600s)"
  default     = "3600s"
}

variable "crawler_task_count" {
  type        = number
  description = "Total number of tasks for Cloud Run Job task array"
  default     = 8
}

variable "crawler_parallelism" {
  type        = number
  description = "Number of tasks executing simultaneously in Cloud Run Job"
  default     = 4
}

variable "schedule_cron" {
  type        = string
  description = "Cron schedule expression in UTC (0 16 * * * is JST 01:00)"
  default     = "0 16 * * *"
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
  description = "New Relic GCP Log Streaming ingest endpoint URL (e.g. https://gcp-api.newrelic.com/log/v1?Api-Key=...)"
  default     = ""
  sensitive   = true
}


