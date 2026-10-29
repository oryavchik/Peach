terraform {
  required_version = ">= 1.10, < 2.0"
  cloud {
    organization = "oryavchik"
    # Never commit an HCP API token.
    workspaces {
      name = "Peach"
    }

  }

  required_providers {
    aws = {
      source = "hashicorp/aws", version = "~> 6.0"
    }

  }

}

provider "aws" {
  region              = var.region
  allowed_account_ids = [var.aws_account_id]
  # Keep empty during adoption. Add ManagedBy via a reviewed post-import run.
  default_tags {
    tags = var.default_tags
  }

}

data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  partition  = data.aws_partition.current.partition
  tags = {
    PROJECT_NAME = var.project_name
  }

  reports_bucket_name = "peach-reports-${local.account_id}-${var.region}"
  lambda_trust = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Action = "sts:AssumeRole", Principal = {
        Service = "lambda.amazonaws.com"
      }
      }
    ]
    }
  )
}

