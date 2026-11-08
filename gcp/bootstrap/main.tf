# Keyless HCP trust bootstrap. Prepared only; never create JSON service-account keys.
terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers { google = { source = "hashicorp/google", version = "~> 7.0" } }
}
variable "project_id" { type = string }
variable "hcp_organization_id" { type = string }
variable "hcp_workspace_id" { type = string }
provider "google" { project = var.project_id }
resource "google_project_service" "identity" {
  for_each           = toset(["iam.googleapis.com", "iamcredentials.googleapis.com", "sts.googleapis.com"])
  service            = each.value
  disable_on_destroy = false
}
resource "google_service_account" "terraform" {
  account_id   = "peach-terraform"
  display_name = "HCP Peach GCP Terraform no permanent keys"
  depends_on   = [google_project_service.identity]
}
resource "google_project_iam_member" "terraform" {
  for_each = toset([
    "roles/serviceusage.serviceUsageAdmin", "roles/firebase.admin",
    "roles/datastore.owner", "roles/iam.serviceAccountAdmin",
    "roles/iam.serviceAccountUser", "roles/resourcemanager.projectIamAdmin"
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.terraform.email}"
}
resource "google_iam_workload_identity_pool" "hcp" {
  workload_identity_pool_id = "peach-hcp"
  display_name              = "Peach HCP short lived deployment identity"
  depends_on                = [google_project_service.identity]
}
resource "google_iam_workload_identity_pool_provider" "hcp" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.hcp.workload_identity_pool_id
  workload_identity_pool_provider_id = "terraform"
  attribute_mapping = {
    "google.subject"         = "assertion.sub"
    "attribute.workspace_id" = "assertion.terraform_workspace_id"
  }
  # Immutable IDs prevent a same-name organization/workspace from gaining trust.
  attribute_condition = "assertion.terraform_organization_id == '${var.hcp_organization_id}' && assertion.terraform_workspace_id == '${var.hcp_workspace_id}'"
  oidc { issuer_uri = "https://app.terraform.io" }
}
resource "google_service_account_iam_member" "hcp" {
  service_account_id = google_service_account.terraform.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.hcp.name}/attribute.workspace_id/${var.hcp_workspace_id}"
}
output "TFC_GCP_WORKLOAD_PROVIDER_NAME" { value = google_iam_workload_identity_pool_provider.hcp.name }
output "TFC_GCP_RUN_SERVICE_ACCOUNT_EMAIL" { value = google_service_account.terraform.email }
