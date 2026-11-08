variable "project_id" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "Use an existing, globally unique GCP project ID."
  }
}
variable "region" { default = "us-central1" }
variable "api_image" {
  type        = string
  default     = null
  description = "linux/amd64 image in this project's Artifact Registry, pinned by digest."
  validation {
    condition     = var.api_image == null ? true : can(regex("@sha256:[a-f0-9]{64}$", var.api_image))
    error_message = "Pin the reviewed backend image by sha256 digest."
  }
}
variable "cognito_pool_id" {
  type    = string
  default = ""
}
variable "cognito_client_id" {
  type    = string
  default = ""
}
variable "cognito_region" { default = "us-east-1" }
variable "hosting_site_id" { type = string }
variable "billing_account_id" {
  type        = string
  default     = null
  description = "Verified Free Trial billing account; never automatically activate a paid account."
}

variable "enable_compute" {
  type        = bool
  default     = false
  description = "Keep false under the owner's no-billing instruction. Cloud Run cannot deploy without billing."
  validation {
    condition     = !var.enable_compute || (var.billing_account_id != null && var.api_image != null && var.cognito_pool_id != "" && var.cognito_client_id != "")
    error_message = "Compute requires separately approved billing, a pinned image and configured token verification."
  }
}
