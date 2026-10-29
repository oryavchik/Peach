# Peach

Next.js task board, meeting management and AI-assisted agenda review.
The original interface is hosted at
https://peach-agenda-free.peach-free-cloud-demo.workers.dev/ using Cloudflare
Workers/D1 and a free OpenRouter model. See [Cloudflare setup](docs/CLOUDFLARE_DEMO.md).

## Local development

```sh
make up
make migrate
make test
make lint
```

For the original interface with the local free-parser adapter, use
`make free-ai-server` and `make free-ai-frontend`. Server secrets belong in
ignored `.env` files, never in `NEXT_PUBLIC_` browser variables.

## Terraform lab: migration prepared, not executed

`infra/auth.tf`, `reports.tf` and `ai.tf` translate the three feature templates.
The older base API/database/site templates stay in CloudFormation, as the lab
allows. The Cloudflare deployment is independent and is not managed by this
AWS Terraform root module.

**No resources have been imported, no stacks released, and no apply executed.**
The owner currently prohibits AWS changes and has not configured HCP Terraform.
The three CloudFormation templates remain with Retain policies until ownership
is safely transferred. Deleting them prematurely would misrepresent completion.

The prepared adoption contains 40 Terraform import targets covering 23 existing
CloudFormation objects and five existing Cognito objects; bucket properties and
role policies/attachments are separate Terraform objects. No recreation is planned.
Actual recreation/import counts are both zero until the migration is performed.

Install Terraform 1.10+ (tested CLI: 1.16.7; locked AWS provider: 6.71.0).
Local syntax checks do not need HCP or AWS writes:

```sh
terraform -chdir=infra init -backend=false
make infra-validate
python3 scripts/test_tf_plan_guard.py
```

After creating an HCP **Free** organization and workspace `Peach`:

```sh
export TF_CLOUD_ORGANIZATION=oryavchik
terraform login
make infra-init
make infra-plan
make infra-outputs
```

`make infra-plan` only plans. There is no apply target. Infrastructure applies
must be reviewed in the VCS-connected HCP workspace. The Free plan supports
up to 500 managed resources; this migration's expected count is 40.
[HCP plan documentation](https://developer.hashicorp.com/terraform/cloud-docs/overview).

**Before any remote import/apply**, follow the complete
[migration runbook](docs/TERRAFORM_MIGRATION.md), including the existing
CloudFormation ownership handoff. A clean validation is not a no-change plan.

## Application deployment after migration

GitHub Actions still builds application images/site assets using AWS OIDC.
HCP Terraform owns feature infrastructure. Enable repository variable
`TERRAFORM_MIGRATION_COMPLETE=true` only after the verified handoff; also set
`TF_CLOUD_ORGANIZATION` and sensitive Actions secret `TF_API_TOKEN` for state
output access. Application scripts then read Cognito/parser configuration with
`terraform output -raw`; they do not apply Terraform.

- `make deploy-cognito`, `deploy-reports` and `deploy-ai` now request plans.
- `make deploy-report-code` / `deploy-parser-code` accept an already built
  immutable `IMAGE_URI=...@sha256:...` and update application code only.
- Lambda `image_uri` is explicitly owned by application CI after adoption;
  Terraform manages configuration and ignores later application image changes.
- Deploy new infrastructure/environment configuration first, then code that
  requires it. Keep backwards compatibility for rolling changes.
- The existing base API/frontend CloudFormation pipelines remain unchanged
  until the feature migration is complete.

## Submission status

1. Terraform source, imports, Retain templates, Makefile/pipeline preparation,
   inventory and [ADR 0007](docs/adr/0007-terraform.md): prepared.
2. VCS-triggered HCP `Apply finished` screenshot: **pending**.
3. Actual post-migration `No changes` plan output: **pending**.

Neither mock plan data nor a local validation is submitted as real migration
evidence. Original YAML files are removed only after a successful handoff and
verified no-change plan. Existing users and reports must be preserved.
