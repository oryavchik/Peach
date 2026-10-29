variable "project_name" {
  type = string
}

variable "aws_account_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "Use the existing 12-digit AWS account ID."
  }
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "default_tags" {
  type    = map(string)
  default = {}
}

variable "frontend_url" {
  type = string
}

variable "cognito_tags" {
  description = "Existing manually created pool has no tags; preserve this during adoption."
  type        = map(string)
  default     = {}
}

variable "cognito_domain_prefix" {
  type = string
}

variable "google_client_id" {
  type = string
}

variable "google_client_secret" {
  type      = string
  sensitive = true
}

variable "report_image_uri" {
  type = string
}

variable "parser_image_uri" {
  type = string
}

variable "report_sender" {
  type      = string
  sensitive = true
}

variable "report_recipients" {
  type      = list(string)
  sensitive = true
}

variable "sender_domain" {
  type    = string
  default = ""
}

variable "budget_email" {
  type      = string
  sensitive = true
}

variable "database_url" {
  description = "Existing Lambda DATABASE_URL, set as a sensitive HCP variable; do not fetch or commit it during inventory."
  type        = string
  sensitive   = true
}

variable "api_execution_role_name" {
  type = string
}

variable "role_names" {
  description = "Exact existing CFN-generated IAM role names; import must not rename them."
  type = object({
    parser = string, builder = string, mailer = string, dispatcher = string, scheduler = string
    }
  )
}

variable "permission_statement_ids" {
  description = "Existing Lambda policy Sids from the CloudFormation physical IDs."
  type = object({
    parser_url = string, parser_invoke = string, mailer = string, dispatcher = string
    }
  )
}

variable "vpc_id" {
  type = string
}

variable "route_table_ids" {
  type = list(string)
}

variable "builder_security_group_ids" {
  type = list(string)
}

variable "builder_subnet_ids" {
  type = list(string)
}

variable "parser_enabled" {
  type    = bool
  default = false
  validation {
    condition     = !var.parser_enabled
    error_message = "Paid Bedrock remains disabled under the owner's no-paid-inference constraint."
  }

}

variable "parser_model" {
  type    = string
  default = "anthropic.claude-opus-5-5"
}

variable "parser_input_price" {
  type    = number
  default = 4.4
}

variable "parser_output_price" {
  type    = number
  default = 22
}

