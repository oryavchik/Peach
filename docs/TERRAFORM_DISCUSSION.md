# Part 2, Step 7 — discussion preparation

1. **Imports and recreations.** At preparation time, actual imports and
   recreations are both zero. Forty explicit import targets are prepared,
   covering the 23 resources in the two existing feature stacks plus five
   Cognito objects. S3 settings and IAM policies/attachments are split into
   separate Terraform objects. No re-creation is intended, including Lambda
   permissions: their existing Sids are used. Report measured counts after the
   actual migration, not these prepared counts as completed work.

2. **Replacement-sensitive fields.** `username_attributes` on the Cognito pool
   and `bucket` on the reports bucket can require replacement. Recreating the
   pool risks losing identities; replacing a bucket changes where reports live
   and can lose data if deletion is forced. `prevent_destroy` blocks such a
   plan, and `force_destroy=false` prevents emptying a reports bucket through
   this configuration. These guards must not be removed to make a plan pass.

3. **Where the Google secret lives.** Its original authorized source, the
   sensitive HCP variable, the configured Cognito provider, Terraform provider
   process memory and Terraform state/backups can contain it. Local private
   tfvars or JSON plans would be additional copies if someone creates them.
   `sensitive=true` masks ordinary output, not the state. State/variable readers,
   AWS administrators, compromised runner processes or exposed backups could
   leak it. Restrict access, protect backups and rotate on disclosure.

4. **Concurrent applies.** One remote state/workspace supplies locking and
   serialized runs. A second operator waits or receives a lock conflict rather
   than writing a competing state. A local state in Git provides neither a
   distributed lock nor an authoritative current copy; two applies can race,
   and a merge cannot repair already-issued cloud API calls. It also exposes
   secrets stored in state.

5. **Narrow trust and permissions.** The bootstrap draft restricts audience to
   `aws.workload.identity` and subject to
   `organization:ORG:project:PROJECT:workspace:peach-dev:run_phase:*`.
   Initial import-only work uses ReadOnlyAccess rather than AdministratorAccess.
   Examples of necessary reads are `lambda:GetFunction`, `iam:GetRolePolicy`
   and `s3:GetBucketNotification`. Later configuration changes may need scoped
   `lambda:UpdateFunctionConfiguration`, `sqs:SetQueueAttributes` and
   `logs:PutRetentionPolicy`; grant them only after review, for project resources.
   Do not grant a wildcard organization/workspace trust just for convenience.

6. **An assistant adding staging.** It should produce parameterized code,
   non-secret stage values, a separate workspace/state design, expected costs,
   a reviewed plan and a PR. It must not repoint the dev state at stage, apply
   infrastructure, delete data, broaden IAM trust or merge its own proposal
   without the team's explicit authorization. Same shape does not mean shared
   state or shared secrets.

**Emergency drift.** If a console change was an intentional incident fix,
capture that desired change and reason in Git/PR before the next apply. Do not
blindly apply the older configuration to erase a valid fix, or permanently
ignore the drift to hide it.
