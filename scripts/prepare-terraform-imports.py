"""Generate adoption files from the checked-in read-only inventory; never calls AWS."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
inventory = json.loads((ROOT / "docs/terraform-evidence/stack-inventory.json").read_text())
functions = json.loads((ROOT / "docs/terraform-evidence/function-artifacts.json").read_text())
auth = json.loads((ROOT / "docs/terraform-evidence/cognito-inventory.json").read_text())
reports = {r["LogicalResourceId"]: r["PhysicalResourceId"] for r in inventory["peach-reports"]["resources"]}
ai = {r["LogicalResourceId"]: r["PhysicalResourceId"] for r in inventory["peach-ai"]["resources"]}
account = functions["peach-backend"]["Role"].split(":")[4]
api_role = functions["peach-backend"]["Role"].rsplit("/", 1)[1]
roles = {"parser": ai["ParserRole"], **{key: reports[logical] for key, logical in {
    "builder": "ReportBuilderRole", "dispatcher": "ReportDispatcherRole",
    "mailer": "ReportMailerRole", "scheduler": "SchedulerRole",
}.items()}}
permissions = {"parser_url": ai["ParserUrlPermission"], "parser_invoke": ai["ParserInvokePermission"],
               "mailer": reports["ReportMailerPermission"], "dispatcher": reports["ReportDispatcherPermission"]}
values = {
    "project_name": "peach", "aws_account_id": account, "region": "us-east-1",
    "frontend_url": "https://d2u4q6uy2ofop2.cloudfront.net",
    "cognito_domain_prefix": f"peach-{account}", "cognito_tags": auth["pool"]["Tags"],
    "default_tags": {}, "parser_enabled": False,
    "report_image_uri": functions["peach-report-builder"]["Image"],
    "parser_image_uri": functions["peach-agenda-parser"]["Image"],
    "api_execution_role_name": api_role, "role_names": roles,
    "permission_statement_ids": permissions,
    "vpc_id": "vpc-021d221c07e003f97", "route_table_ids": ["rtb-05f63be5ef0440b79"],
    "builder_security_group_ids": ["sg-0594b79a6a59c8e79"],
    "builder_subnet_ids": ["subnet-0a79e656ccbd43018", "subnet-09d34893c725a9f3d", "subnet-0926d5aeef6819cbe", "subnet-0b7a453d7e0f30ebe", "subnet-0e408246861281045"],
}
pool = auth["pool"]["Id"]
imports = {
    "aws_cognito_user_pool.main": pool,
    "aws_cognito_identity_provider.google": f"{pool}:Google",
    "aws_cognito_user_pool_client.web": f"{pool}/{auth['client']['ClientId']}",
    "aws_cognito_user_pool_domain.main": values["cognito_domain_prefix"],
    "aws_cognito_managed_login_branding.web": f"{pool},{auth['branding']['ManagedLoginBrandingId']}",
    "aws_s3_bucket.reports": reports["ReportsBucket"],
    "aws_s3_bucket_public_access_block.reports": reports["ReportsBucket"],
    "aws_s3_bucket_lifecycle_configuration.reports": reports["ReportsBucket"],
    "aws_s3_bucket_notification.reports": reports["ReportsBucket"],
    "aws_sqs_queue.reports": reports["ReportsQueue"],
    "aws_sqs_queue.dlq": reports["ReportsDLQ"],
    "aws_vpc_endpoint.s3": reports["S3GatewayEndpoint"],
    "aws_iam_role_policy.api_report_requests": f"{api_role}:PeachReportRequests",
    "aws_lambda_event_source_mapping.reports": reports["ReportsEventSource"],
    "aws_scheduler_schedule.weekly": f"default/{reports['WeeklySchedule']}",
    "aws_iam_role.parser": roles["parser"],
    "aws_iam_role_policy.parser_inference": f"{roles['parser']}:InferenceOnly",
    "aws_iam_role_policy_attachment.parser_logs": f"{roles['parser']}/arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    "aws_cloudwatch_log_group.parser": ai["ParserLogGroup"],
    "aws_lambda_function.parser": ai["Parser"],
    "aws_lambda_function_url.parser": ai["Parser"],
    "aws_lambda_permission.parser_url": f"{ai['Parser']}/{permissions['parser_url']}",
    "aws_lambda_permission.parser_invoke": f"{ai['Parser']}/{permissions['parser_invoke']}",
    "aws_budgets_budget.ai": f"{account}:{ai['MonthlyBudget']}",
}
policy_names = {"builder": "ReportsAccess", "dispatcher": "RequestDispatch", "mailer": "MailerAccess", "scheduler": "SendReportsMessage"}
for key in ["builder", "dispatcher", "mailer", "scheduler"]:
    imports[f'aws_iam_role.reports["{key}"]'] = roles[key]
    imports[f'aws_iam_role_policy.reports["{key}"]'] = f"{roles[key]}:{policy_names[key]}"
    if key != "scheduler":
        managed = "AWSLambdaVPCAccessExecutionRole" if key == "builder" else "AWSLambdaBasicExecutionRole"
        imports[f'aws_iam_role_policy_attachment.reports["{key}"]'] = f"{roles[key]}/arn:aws:iam::aws:policy/service-role/{managed}"
        imports[f'aws_lambda_function.reports["{key}"]'] = f"peach-report-{key}"
for key in ["mailer", "dispatcher"]:
    imports[f'aws_lambda_permission.s3_reports["{key}"]'] = f"peach-report-{key}/{permissions[key]}"

for name in ["imports.tf", "terraform.tfvars"]:
    if (ROOT / "infra" / name).exists():
        raise SystemExit(f"Refusing to overwrite reviewed infra/{name}; move it aside explicitly first.")
(ROOT / "infra/terraform.tfvars").write_text(
    "# Non-secret existing values only. Set sensitive values in HCP workspace variables.\n"
    + "\n".join(f"{key} = {json.dumps(value)}" for key, value in values.items()) + "\n"
)
(ROOT / "infra/imports.tf").write_text(
    "# Prepared only. Do not apply while CloudFormation still owns the resources.\n"
    + "\n".join(f"import {{\n  to = {address}\n  id = {json.dumps(identity)}\n}}\n" for address, identity in imports.items())
)
(ROOT / "docs/terraform-evidence/import-map.json").write_text(json.dumps(imports, indent=2) + "\n")
print(f"Prepared {len(imports)} import blocks. Actual imports performed: 0.")
