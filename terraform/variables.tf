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
  description = "Execution timeout for Cloud Run Job (up to 24h: 86400s)"
  default     = "86400s"
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

