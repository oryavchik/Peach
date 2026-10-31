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

## Terraform lab: migration verified

Feature infrastructure is managed by `infra/auth.tf`, `reports.tf` and `ai.tf`
in HCP organization `oryavchik`, workspace `Peach`. The base API/database/site
stacks remain in CloudFormation. The independent Cloudflare deployment is unchanged.

The owner confirmed the VCS-triggered import apply. All **40 Terraform resources**
were imported; none were recreated. Both former feature stack containers were
released after verified Retain-only updates; all 23 CloudFormation resources
were retained. The five Cognito objects were adopted in place. Temporary import
blocks and the three feature YAML templates were removed after a real HCP
post-import plan verified zero imports, updates, creates, deletes or output changes.

Evidence: [apply result](docs/terraform-evidence/hcp-import-result.json),
[no-change output](docs/terraform-evidence/NO_CHANGES.txt), and
[ADR 0007](docs/adr/0007-terraform.md). Saved state/plans and credentials are never committed.

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

## Submission

1. Submit the final migration commit containing Terraform, the Makefile, this README
   and [ADR 0007](docs/adr/0007-terraform.md).
2. Open [the owner-approved VCS run](https://app.terraform.io/app/oryavchik/workspaces/Peach/runs/run-EgM4hPVixxmAJ2rT)
   and capture its **Apply finished** screen. API status confirms it finished;
   a screenshot must still be captured by the owner.
3. Attach [the actual HCP no-change output](docs/terraform-evidence/NO_CHANGES.txt)
   and its [verification summary](docs/terraform-evidence/hcp-no-changes.json).

## Lab 8: free local batch/streaming work

See [the implementation](labs/lab8/README.md) and [real results](docs/lab8-evidence/RESULTS.md).
All five local Redpanda experiments ran on the provided real October 1 dataset.
Local DuckDB CSVs are explicitly one-day cross-checks, not Athena results.
The owner prohibits cloud charges: Part 2 AWS measurements and Part 4 AWS
execution/screenshot remain outstanding. SQL, cloud code and an undeployed
pipeline diagram are prepared separately; no cloud resources were created.
