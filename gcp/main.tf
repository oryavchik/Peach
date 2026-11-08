locals {
  free_apis = toset(["firebase.googleapis.com", "firebasehosting.googleapis.com", "firestore.googleapis.com", "firebaserules.googleapis.com", "iam.googleapis.com"])
  apis      = var.enable_compute ? setunion(local.free_apis, toset(["run.googleapis.com", "artifactregistry.googleapis.com", "logging.googleapis.com", "billingbudgets.googleapis.com"])) : local.free_apis
}
resource "google_project_service" "api" {
  for_each           = local.apis
  service            = each.value
  disable_on_destroy = false
}
resource "google_billing_budget" "lab" {
  count           = var.enable_compute ? 1 : 0
  billing_account = var.billing_account_id
  display_name    = "Peach Lab9 monitoring only not a spending cap"
  budget_filter { projects = ["projects/${data.google_project.current.number}"] }
  amount {
    specified_amount {
      currency_code = "USD"
      units         = "5"
    }
  }
  threshold_rules { threshold_percent = 0.5 }
  threshold_rules { threshold_percent = 0.9 }
  threshold_rules { threshold_percent = 1.0 }
  depends_on = [google_project_service.api]
}
data "google_project" "current" {}
resource "google_artifact_registry_repository" "api" {
  count         = var.enable_compute ? 1 : 0
  location      = var.region
  repository_id = "peach-api"
  format        = "DOCKER"
  description   = "Small Peach Cloud Run backend only"
  depends_on    = [google_project_service.api]
}
resource "google_service_account" "api" {
  count        = var.enable_compute ? 1 : 0
  account_id   = "peach-api"
  display_name = "Peach Cloud Run runtime only"
  depends_on   = [google_project_service.api]
}
resource "google_project_iam_member" "database" {
  count   = var.enable_compute ? 1 : 0
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.api[0].email}"
}
resource "google_firestore_database" "main" {
  name                              = "(default)"
  location_id                       = var.region
  type                              = "FIRESTORE_NATIVE"
  delete_protection_state           = "DELETE_PROTECTION_ENABLED"
  deletion_policy                   = "ABANDON"
  point_in_time_recovery_enablement = "POINT_IN_TIME_RECOVERY_DISABLED"
  depends_on                        = [google_project_service.api]
}
resource "google_firebaserules_ruleset" "deny_browser_access" {
  source {
    files {
      name    = "firestore.rules"
      content = <<-RULES
        rules_version = '2';
        service cloud.firestore {
          match /databases/{database}/documents {
            match /{document=**} { allow read, write: if false; }
          }
        }
      RULES
    }
  }
  depends_on = [google_project_service.api]
}
resource "google_firebaserules_release" "database" {
  name         = "cloud.firestore"
  ruleset_name = google_firebaserules_ruleset.deny_browser_access.name
  depends_on   = [google_firestore_database.main]
}
resource "google_cloud_run_v2_service" "api" {
  count               = var.enable_compute ? 1 : 0
  name                = "peach-api"
  location            = var.region
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"
  template {
    service_account                  = google_service_account.api[0].email
    max_instance_request_concurrency = 20
    timeout                          = "60s"
    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }
    containers {
      image = var.api_image
      ports { container_port = 8080 }
      resources {
        limits            = { cpu = "1", memory = "512Mi" }
        cpu_idle          = true
        startup_cpu_boost = false
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "COGNITO_POOL_ID"
        value = var.cognito_pool_id
      }
      env {
        name  = "COGNITO_CLIENT_ID"
        value = var.cognito_client_id
      }
      env {
        name  = "COGNITO_REGION"
        value = var.cognito_region
      }
      env {
        name  = "FRONTEND_ORIGIN"
        value = "https://${var.hosting_site_id}.web.app"
      }
    }
  }
  depends_on = [google_project_service.api, google_project_iam_member.database, google_firestore_database.main]
}
# Cloud Run is public at the transport layer; business routes verify Cognito
# JWT signature, issuer, audience, expiry and token_use before any data access.
resource "google_cloud_run_v2_service_iam_member" "browser" {
  count    = var.enable_compute ? 1 : 0
  location = var.region
  name     = google_cloud_run_v2_service.api[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
resource "google_firebase_project" "main" {
  provider   = google-beta
  depends_on = [google_project_service.api]
}
resource "google_firebase_hosting_site" "frontend" {
  provider   = google-beta
  site_id    = var.hosting_site_id
  depends_on = [google_firebase_project.main]
}
output "api_url" { value = var.enable_compute ? google_cloud_run_v2_service.api[0].uri : null }
output "frontend_url" { value = "https://${google_firebase_hosting_site.frontend.site_id}.web.app" }
