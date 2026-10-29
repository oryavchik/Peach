# Separate local bootstrap state. Not called from the root module or Makefile.
# The assistant must never apply this; owner review is required.
terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}
variable "organization" { type = string }
variable "project" {
  type    = string
  default = "Default Project"
}
variable "workspace" {
  type    = string
  default = "Peach"
}
variable "aws_account_id" { type = string }
provider "aws" {
  region              = "us-east-1"
  allowed_account_ids = [var.aws_account_id]
}
resource "aws_iam_openid_connect_provider" "hcp" {
  url            = "https://app.terraform.io"
  client_id_list = ["aws.workload.identity"]
}
resource "aws_iam_role" "hcp" {
  name = "hcp-terraform-Peach"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.hcp.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = { "app.terraform.io:aud" = "aws.workload.identity" }
        StringLike = {
          "app.terraform.io:sub" = "organization:${var.organization}:project:${var.project}:workspace:${var.workspace}:run_phase:*"
        }
      }
    }]
  })
}
resource "aws_iam_role_policy_attachment" "read_only_import" {
  role       = aws_iam_role.hcp.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}
output "hcp_role_arn" { value = aws_iam_role.hcp.arn }
