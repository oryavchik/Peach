# 0007 — Adopt existing feature infrastructure into Terraform and HCP

## Context

Authentication, reports and parsing were described in three CloudFormation
templates. The project also uses GitHub and Cloudflare. We need reviewable,
parameterized infrastructure, central state and a migration that preserves
user accounts, reports and resource names. The current owner permits code
preparation and read-only inventory but prohibits AWS changes/paid inference.

## Decision

Prepare one AWS Terraform root module in `infra/`, with `auth.tf`, `reports.tf`,
`ai.tf`, non-secret variables and an HCP workspace `peach-dev`. Use an HCP
organization supplied by the owner, remote execution, versioned/locked state,
VCS-triggered plans, and human-reviewed remote applies. The assistant does not
run apply or delete stacks. Keep the existing base API/database/site stacks.

Adopt the existing resources with explicit import blocks and unchanged names.
Forty import targets are prepared; no imports have been performed. Before
release, review/deploy Retain-only updates to the currently owning stacks;
verify retention, release ownership, then review an import-only plan. Do not
let CloudFormation and Terraform manage the same resource concurrently.
Critical resources have `prevent_destroy`; reports use `force_destroy=false`.
Remove the original templates/import blocks only after successful adoption and
a real no-change plan. The absent auth stack requires separate ownership checks.

Application CI keeps the existing GitHub OIDC path and owns Lambda image
updates. Terraform owns function configuration; image changes from CI are
explicitly ignored. After migration, application scripts read state outputs.
Infrastructure needed by a new application version must be deployed first.

## Alternatives

- Keep CloudFormation: AWS-managed state and rollback are useful, but it does
  not provide the common multi-provider workflow chosen for this course/project.
- AWS CDK: convenient typed constructs, but still synthesizes CloudFormation
  and keeps the same AWS scope and migration constraints.
- OpenTofu: a valid open-source alternative. Terraform is chosen to match the
  assessed HCP/VCS workflow and tested CLI/provider combination; no claim that
  OpenTofu cannot manage these AWS resources is intended.
- Re-create resources: rejected because it risks user identities, reports,
  names, queue messages and service availability.

## Consequences

HCP workspace writers can propose changes through repository PRs. Authorized
reviewers approve remote applies after reviewing the plan; HCP/AWS role access
must be restricted to the workspace. The bootstrap draft uses an exact
organization/project/workspace OIDC subject and ReadOnlyAccess for initial
import-only work, not AdministratorAccess. Later writes require reviewed,
service/resource-scoped permissions. No bootstrap is applied by the assistant.

Google OAuth secret, database URL and email settings are sensitive HCP Terraform
variables. They are also present wherever AWS stores the configured values
(Cognito provider details/Lambda environment) and in Terraform state/provider
data as applicable. `sensitive=true` hides UI output; it does not remove secrets
from state. Restrict state, token and variable access; protect backups; do not
commit states, private tfvars or saved JSON plans. Cloud credentials are
short-lived OIDC credentials; no AWS access keys are placed in HCP or Git.

If HCP is down, deployed services keep running. Infrastructure changes wait.
Do not create a second local state or bypass locking. A genuine emergency needs
an authorized, documented recovery using the same authoritative state, with
review and reconciliation afterward.

Status: translation/validation preparation only. HCP setup, bootstrap, ownership
release, imports, real no-change output, drift exercise and VCS apply screenshot
are pending. The live free Cloudflare app is not changed by this migration.
