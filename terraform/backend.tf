terraform {
  backend "gcs" {
    bucket = "sumifu-terraform-state"
    prefix = "realestate-crawler/prod"
  }
}
