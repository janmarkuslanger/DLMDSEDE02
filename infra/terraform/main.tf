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

# --- Least privilege: one user + policy per service -------------------------

variable "ingestion_secret" {
  type      = string
  sensitive = true
}

variable "spark_secret" {
  type      = string
  sensitive = true
}

variable "orchestration_secret" {
  type      = string
  sensitive = true
}

locals {
  arn = "arn:aws:s3:::"

  # Policy per service. Object actions on "<bucket>/*", bucket actions on "<bucket>".
  policies = {
    # Ingestion: writes bronze and quarantine, nothing else.
    ingestion = [
      {
        actions   = ["s3:PutObject", "s3:DeleteObject", "s3:AbortMultipartUpload"]
        resources = ["${local.arn}bronze/*", "${local.arn}quarantine/*"]
      },
    ]
    # Spark: reads bronze, reads/writes silver and gold (S3A needs list + delete for commits).
    spark = [
      {
        actions   = ["s3:GetObject"]
        resources = ["${local.arn}bronze/*"]
      },
      {
        actions = [
          "s3:GetObject", "s3:PutObject", "s3:DeleteObject",
          "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts",
        ]
        resources = ["${local.arn}silver/*", "${local.arn}gold/*"]
      },
      {
        actions   = ["s3:ListBucket", "s3:GetBucketLocation", "s3:ListBucketMultipartUploads"]
        resources = ["${local.arn}bronze", "${local.arn}silver", "${local.arn}gold"]
      },
    ]
    # Orchestration: may only list bronze (to check that a month has been ingested).
    orchestration = [
      {
        actions   = ["s3:ListBucket"]
        resources = ["${local.arn}bronze"]
      },
    ]
  }

  secrets = {
    ingestion     = var.ingestion_secret
    spark         = var.spark_secret
    orchestration = var.orchestration_secret
  }
}

resource "minio_iam_policy" "service" {
  for_each = local.policies
  name     = each.key
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [for s in each.value : {
      Effect   = "Allow"
      Action   = s.actions
      Resource = s.resources
    }]
  })
}

resource "minio_iam_user" "service" {
  for_each      = local.secrets
  name          = each.key
  secret        = each.value
  force_destroy = true
}

resource "minio_iam_user_policy_attachment" "service" {
  for_each    = local.secrets
  user_name   = minio_iam_user.service[each.key].name
  policy_name = minio_iam_policy.service[each.key].name
}
