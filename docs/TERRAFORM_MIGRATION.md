# CloudFormation → Terraform migration runbook

## Current status and authorization

The owner-authorized migration is complete. Retain-only updates were verified
and the two stack containers released with all 23 resources preserved. The owner
confirmed the VCS-triggered HCP apply `run-EgM4hPVixxmAJ2rT`, which imported all
40 Terraform objects. No resources were recreated. The subsequent remote
plan-only run `run-shqNo6KtbUHjrpiM` passed the strict no-change guard: 40 managed
objects, zero imports/updates/creates/deletes and no output changes. Temporary
import blocks and the three feature YAML files were removed after verification.
The following sections retain the reviewed operational procedure as a record;
do not repeat completed release/import steps. The owner still needs to capture
the Apply finished screenshot from the linked HCP run.

The former `peach-reports` and `peach-ai` stacks contained 16 and 7 resources.
`peach-auth` is absent; the named Cognito pool/client/Google provider/branding
exist. Verify the domain and whether any other stack owns those resources
before adoption. Do not create a second pool because an auth stack is absent.

Forty Terraform objects cover those 28 existing objects, with S3 settings and
IAM inline policies/attachments decomposed. See `import-map.json`. The optional
SES domain is absent and stays `count=0`. Re-created objects: none planned.
Actual imports: 40. Actual re-creations: zero.

## 1. HCP setup

1. Create an HCP Terraform Free organization. Create workspace **Peach** in
   Remote execution mode, pinned to Terraform 1.16.7, with working directory
   `infra`. Connect this GitHub repository and choose the reviewed target branch.
2. Keep automatic apply **off** during migration. Freeze feature-stack changes
   in old CI/console paths and use a maintenance window for the ownership transfer.
3. The root `cloud` block targets organization `oryavchik` and workspace `Peach`
   for CLI operations. Use `terraform login` locally; never paste the token in Git/chat.
4. Set sensitive Terraform variables in the workspace:
   `google_client_secret`, `database_url`, `report_sender`, `report_recipients`
   (HCL list), `budget_email`. Set `google_client_id` as a Terraform variable.
   Copy existing values through authorized channels; do not invent placeholders
   or commit them. All non-secret values are in `infra/terraform.tfvars`.
5. Review the separate `infra/bootstrap` configuration. It is local-bootstrap
   code only, not part of the root module. Verify whether the OIDC provider
   already exists before creating/importing it. The owner performs any approved
   bootstrap; the assistant never applies it. Preserve/protect its separate state.
6. Set HCP environment variables `TFC_AWS_PROVIDER_AUTH=true` and
   `TFC_AWS_RUN_ROLE_ARN=<reviewed role ARN>`. The role trust must identify this
   exact organization/project/workspace. Start with read-only AWS permissions
   for an import-only run. Broader write permissions are a separate review.

The current bootstrap deliberately does not grant AdministratorAccess.
[HCP dynamic AWS credentials](https://developer.hashicorp.com/terraform/cloud-docs/workspaces/dynamic-provider-credentials/aws-configuration).

## 2. Check the code and identity

```sh
aws sts get-caller-identity
terraform -chdir=infra init -backend=false
terraform -chdir=infra fmt -check
terraform -chdir=infra validate
python3 scripts/test_tf_plan_guard.py
```

The provider restricts the AWS account ID. Inventory timestamps/IDs, IAM names,
policy Sids, image digests, subnet/route-table associations and Cognito defaults
must still be compared with the real remote plan. Source validation is not proof
of zero drift. In particular, existing manual Cognito has no tags: it must not
gain new default tags during the import. Add `ManagedBy` only in a later PR.

`scripts/prepare-terraform-imports.py` generated the adoption files from recorded
inventory. It refuses to overwrite reviewed files. Re-inventory before an actual
handoff; do not trust stale snapshots or regenerated HCL without review.

## 3. Release CloudFormation ownership safely

Only an explicitly authorized operator performs this phase. Do not start it
until HCP access, variables, imports and a rollback/re-adoption plan are ready.

For each existing owning stack, first prepare its **currently deployed**
template with only retention metadata changed:

```sh
python3 scripts/prepare-retain-template.py peach-reports --output .local/terraform-handoff/reports.retained.yml
python3 scripts/prepare-retain-template.py peach-ai --output .local/terraform-handoff/ai.retained.yml
```

The script only calls GetTemplate and writes an ignored private candidate.
Review it against the live template. A later operator creates/reviews a
CloudFormation change set with existing parameter values, deploys this
Retain-only update, and verifies **every** resource has both
`DeletionPolicy: Retain` and `UpdateReplacePolicy: Retain` in the deployed
template. Capture existing IDs/permissions before releasing anything.

Only then may the authorized operator delete the owning **stacks**, wait for
completion and confirm every retained resource still exists. No destroy/apply
script is supplied to perform that automatically. For Cognito, find its actual
owner first; an absent `peach-auth` stack is not a reason to delete its pool.
Do not remove the resources themselves, empty reports buckets or change names.

## 4. Review/import in HCP

Push the reviewed import configuration; use the VCS-started HCP run. The target
is **40 to import, 0 to add, 0 to change, 0 to destroy**, not an assertion that
this plan has already been obtained. Fix HCL differences rather than applying
them as part of adoption. Reject replacements, updates, creates and deletes.

The plan guard checks a private JSON export of the actual plan:

```sh
python3 scripts/tf_plan_guard.py .local/migration.plan.json --mode import-only
```

It also checks the expected managed-object count, so an empty configuration
cannot fake a no-change result. Saved plans/state can contain secrets: keep
them ignored and access-controlled. `prevent_destroy` is a backstop, not a
substitute for reviewing the full plan. The owner reviews and approves the
remote import-only apply; the assistant must not run it.

There is no planned permission/notification re-creation: existing policy Sids
and the complete S3 notification configuration have explicit import targets.
If a provider truly cannot import one in the real run, stop, document the exact
exception, availability risk and recovery path, and seek separate review.

## 5. Verify, then retire legacy ownership

Run another real HCP plan. It must report:

```text
No changes. Your infrastructure matches the configuration.
```

The text above is the required target, **not measured output**. Save actual
run output in the evidence folder after completion. A private JSON plan can
be checked with `--mode no-changes`. Verify existing login, reports, queues,
notification delivery and the disabled parser state. No paid inference is needed.

Only after that verification remove `imports.tf`, any generated drafts, and
`infra/auth.yaml`, `infra/reports.yml`, `infra/ai.yml` in a reviewed commit.
They remain now because no handoff occurred. Base API/database/site templates
stay CloudFormation-managed. Never delete the retained resources themselves.

Enable repository variable `TERRAFORM_MIGRATION_COMPLETE=true`, set
`TF_CLOUD_ORGANIZATION`, and add sensitive Actions secret `TF_API_TOKEN` for
read access to outputs. Feature deploy targets now plan; application image
deployments read function names from Terraform and do not apply infrastructure.
Deploy infrastructure required by new code first, then the application code.

## 6. Required evidence and drift exercise

- Commit/PR with the completed replacement, Makefile, README and ADR 0007.
- Screenshot of **Apply finished** for this workspace, with a VCS push/merge
  as its source. A CLI-triggered run does not satisfy the requirement.
- Actual post-migration no-change plan output.

For the VCS proof, choose a reviewed harmless tag change only after appropriate
AWS permission and owner authorization; do not change costs or enable Bedrock.
For the drift exercise, the operator makes an approved reversible change, runs
a Plan-only HCP run and reviews the proposed reconciliation. If the manual
change was a real emergency fix, commit that intended fix to Git before the
next apply rather than blindly reverting it. None of these actions has been
executed under the current no-AWS-changes constraint.

## Read-only reconciliation findings

The local read-only adoption plan recorded in
`docs/terraform-evidence/adoption-plan-summary.json` now has 40 imports, no
creates/deletes, and four updates whose before/after values are identical.
Terraform marks imported Google credentials, Lambda environment values and
budget notification addresses as sensitive. These metadata-only updates are
not a final no-change plan and the strict guard still rejects them. Do not
remove sensitivity, ignore live configuration drift, or approve an apply
merely to make the counter green. Review the actual HCP plan and finish the
retained-stack ownership transfer before an owner-approved import.

The Cognito client replacement was caused by imported `generate_secret = null`
versus explicit `false`; omitting that optional argument preserves the imported
client without changing `prevent_destroy`. Other differences reconciled to AWS:
password symbols enabled; Google discovery fields and username mapping; SQS
1 MiB maximum messages; event-source mapping tags; exact Scheduler JSON input.
