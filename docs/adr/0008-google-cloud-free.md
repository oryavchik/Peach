# Google Cloud migration under a no billing constraint

Date: 2026-11-07. Status: accepted for preparation; full migration not deployed.

## Context

Peach runs on AWS with separate Terraform state. Lab 9 requests a GCP core
(frontend, API, database), service mapping, cost comparison and three demos.
The owner explicitly declined connecting any GCP billing account, including a
trial. Project peach-510910 has billingEnabled=false. No billing account is
created or linked, and no long-lived service-account key is downloaded.

## Service decisions

| Current AWS piece | GCP decision | Reason and difference |
|---|---|---|
| S3 CloudFront WAF frontend | Firebase Hosting Spark | Static hosting with managed HTTPS; bounded free transfer/storage. Not a custom Cloud Storage HTTPS load balancer. |
| Lambda FastAPI function URL | Cloud Run configuration only | Cloud Run needs billing even within free usage. Disabled by default; not deployed. |
| ECR | Artifact Registry only if compute separately authorized | No image repository is created under no billing mode. |
| Aurora PostgreSQL | Prefer Firestore for a future free implementation | Avoid always-running Cloud SQL; requires a real data-access rewrite, not an SQL driver swap. |
| DynamoDB alternative | Firestore Native default database | Daily free operations; bounded documents and ownership paths needed. |
| Cognito Google sign-in | Keep on AWS for the core migration | Existing token verification and callback registration still needed; not silently removed. |
| EventBridge Scheduler | Keep AWS weekly reporting | Stretch goal. No GCP scheduler needed for the core. |
| SQS | Keep AWS reporting queue | Pub/Sub or Cloud Tasks are future alternatives; different delivery/order semantics. |
| S3 events Lambda | Keep existing AWS report storage/handlers | Moving only the database would require report data synchronization; not claimed solved. |
| SES | Keep SES | No native drop-in GCP email service; do not introduce a paid mail provider or new key. |
| Bedrock agenda parser | Keep existing parser | Vertex AI comparison is a separate demo and requires billing/credits for actual calls. |
| Parameter Store Secrets Manager | No database password for Firestore | IAM-based access; Secret Manager only if a future integration needs a secret. |
| CloudWatch | Cloud Logging when Cloud Run is authorized | No running API means no GCP request logs claimed. |
| IAM role | Dedicated runtime service account | datastore.user only; never use default Compute Editor identity. |
| Terraform AWS provider | google/google-beta in gcp/ | Separate Peach-GCP workspace, never mix AWS and GCP state. |

## Database tradeoffs

Cloud SQL preserves SQLAlchemy, joins and migrations but bills compute while
running and storage while stopped. Stopping nightly reduces compute but adds
scheduling and availability constraints. Firestore can have zero idle cost
within its free quota, but tables, foreign keys, joins and Alembic migrations
must be replaced by explicit documents and queries. List pages and stats must
avoid scanning every record, because the code controls billed document reads.
Keeping Aurora and calling across clouds minimizes code changes but retains
AWS dependencies, network latency/egress and does not meet the database-move
requirement. No existing personal data are copied into GCP in this run.

## Authentication and state

Developer login uses gcloud short-lived user credentials. HCP bootstrap uses
OIDC issuer app.terraform.io and immutable organization/workspace IDs; only
that workspace may impersonate its Terraform service account. No JSON keys.
The prepared bootstrap does not use Owner/Editor. Project IAM administration
is restricted to the deployment identity because Terraform manages runtime
role bindings; it is not a runtime permission. It has not been applied.

## Consequences and actual scope

BigQuery Sandbox was actually queried without billing. The Cloud Run/FastAPI
migration, Firestore data-access rewrite, HCP workspace bootstrap and live
frontend/database acceptance test are not complete. Firebase availability is
being checked; a placeholder page is not evidence of migrating Peach.
Looker Studio, Vision/Document AI OCR, Gemini and Dataflow runs must not be
claimed without actual execution. A local OCR result is not Vision OCR.
This ADR documents a constrained partial lab, not full rubric completion.

## References checked 2026-11-07

- https://docs.cloud.google.com/free/docs/free-cloud-features
- https://cloud.google.com/run/pricing
- https://cloud.google.com/firestore/pricing
- https://firebase.google.com/docs/projects/billing/firebase-pricing-plans
- https://cloud.google.com/bigquery/docs/sandbox
- https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines
- https://developer.hashicorp.com/terraform/cloud-docs/dynamic-provider-credentials/gcp-configuration

## Update 2026-11-08

Firestore Native Standard default database was actually created without billing; the Admin API returned freeTier=true. A synthetic document was written and read successfully through authenticated REST. No production data migration or Firestore FastAPI adapter is claimed. Deletion protection is enabled; Terraform must import this existing database before apply. Firebase addFirebase still returns 403.
