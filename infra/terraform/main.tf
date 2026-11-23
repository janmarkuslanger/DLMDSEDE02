terraform {
  required_providers {
    minio = {
      source  = "aminueza/minio"
      version = "~> 3.0"
    }
  }
}

variable "minio_endpoint" {
  type = string
}

variable "minio_user" {
  type = string
}

variable "minio_password" {
  type      = string
  sensitive = true
}

provider "minio" {
  minio_server   = var.minio_endpoint
  minio_user     = var.minio_user
  minio_password = var.minio_password
  minio_ssl      = false
}

# One bucket per medallion layer, so policies can later be scoped per service.
locals {
  buckets = toset(["bronze", "silver", "gold", "quarantine"])
}

resource "minio_s3_bucket" "layer" {
  for_each = local.buckets
  bucket   = each.key
  acl      = "private"
}
