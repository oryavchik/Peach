# Prepared only. Do not apply while CloudFormation still owns the resources.
import {
  to = aws_cognito_user_pool.main
  id = "us-east-1_0mtP1IR3E"
}

import {
  to = aws_cognito_identity_provider.google
  id = "us-east-1_0mtP1IR3E:Google"
}

import {
  to = aws_cognito_user_pool_client.web
  id = "us-east-1_0mtP1IR3E/2p3i99e7rbukboqojfrdmdsfcl"
}

import {
  to = aws_cognito_user_pool_domain.main
  id = "peach-506126098984"
}

import {
  to = aws_cognito_managed_login_branding.web
  id = "us-east-1_0mtP1IR3E,26653d9e-92c2-41d1-bd36-02d61014b25f"
}

import {
  to = aws_s3_bucket.reports
  id = "peach-reports-506126098984-us-east-1"
}

import {
  to = aws_s3_bucket_public_access_block.reports
  id = "peach-reports-506126098984-us-east-1"
}

import {
  to = aws_s3_bucket_lifecycle_configuration.reports
  id = "peach-reports-506126098984-us-east-1"
}

import {
  to = aws_s3_bucket_notification.reports
  id = "peach-reports-506126098984-us-east-1"
}

import {
  to = aws_sqs_queue.reports
  id = "https://sqs.us-east-1.amazonaws.com/506126098984/peach-reports-queue"
}

import {
  to = aws_sqs_queue.dlq
  id = "https://sqs.us-east-1.amazonaws.com/506126098984/peach-reports-dlq"
}

import {
  to = aws_vpc_endpoint.s3
  id = "vpce-0284e281ee1dec046"
}

import {
  to = aws_iam_role_policy.api_report_requests
  id = "peach-backend-ExecutionRole-Wl1ccFq0TkVC:PeachReportRequests"
}

import {
  to = aws_lambda_event_source_mapping.reports
  id = "a3d73f56-fb3b-44d6-9631-1c7e6efc0df8"
}

import {
  to = aws_scheduler_schedule.weekly
  id = "default/peach-weekly-reports"
}

import {
  to = aws_iam_role.parser
  id = "peach-ai-ParserRole-mdEJTPrrjCyy"
}

import {
  to = aws_iam_role_policy.parser_inference
  id = "peach-ai-ParserRole-mdEJTPrrjCyy:InferenceOnly"
}

import {
  to = aws_iam_role_policy_attachment.parser_logs
  id = "peach-ai-ParserRole-mdEJTPrrjCyy/arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

import {
  to = aws_cloudwatch_log_group.parser
  id = "/aws/lambda/peach-agenda-parser"
}

import {
  to = aws_lambda_function.parser
  id = "peach-agenda-parser"
}

import {
  to = aws_lambda_function_url.parser
  id = "peach-agenda-parser"
}

import {
  to = aws_lambda_permission.parser_url
  id = "peach-agenda-parser/peach-ai-ParserUrlPermission-dAUemKhv75YW"
}

import {
  to = aws_lambda_permission.parser_invoke
  id = "peach-agenda-parser/peach-ai-ParserInvokePermission-6gmcuLalkY98"
}

import {
  to = aws_budgets_budget.ai
  id = "506126098984:peach-ai-lab-monthly-5usd"
}

import {
  to = aws_iam_role.reports["builder"]
  id = "peach-reports-ReportBuilderRole-p9u0vZcfwAEd"
}

import {
  to = aws_iam_role_policy.reports["builder"]
  id = "peach-reports-ReportBuilderRole-p9u0vZcfwAEd:ReportsAccess"
}

import {
  to = aws_iam_role_policy_attachment.reports["builder"]
  id = "peach-reports-ReportBuilderRole-p9u0vZcfwAEd/arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

import {
  to = aws_lambda_function.reports["builder"]
  id = "peach-report-builder"
}

import {
  to = aws_iam_role.reports["dispatcher"]
  id = "peach-reports-ReportDispatcherRole-ROSvpWdj7aol"
}

import {
  to = aws_iam_role_policy.reports["dispatcher"]
  id = "peach-reports-ReportDispatcherRole-ROSvpWdj7aol:RequestDispatch"
}

import {
  to = aws_iam_role_policy_attachment.reports["dispatcher"]
  id = "peach-reports-ReportDispatcherRole-ROSvpWdj7aol/arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

import {
  to = aws_lambda_function.reports["dispatcher"]
  id = "peach-report-dispatcher"
}

import {
  to = aws_iam_role.reports["mailer"]
  id = "peach-reports-ReportMailerRole-AybCF4Y51FJj"
}

import {
  to = aws_iam_role_policy.reports["mailer"]
  id = "peach-reports-ReportMailerRole-AybCF4Y51FJj:MailerAccess"
}

import {
  to = aws_iam_role_policy_attachment.reports["mailer"]
  id = "peach-reports-ReportMailerRole-AybCF4Y51FJj/arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

import {
  to = aws_lambda_function.reports["mailer"]
  id = "peach-report-mailer"
}

import {
  to = aws_iam_role.reports["scheduler"]
  id = "peach-reports-SchedulerRole-On6szH2RLPvB"
}

import {
  to = aws_iam_role_policy.reports["scheduler"]
  id = "peach-reports-SchedulerRole-On6szH2RLPvB:SendReportsMessage"
}

import {
  to = aws_lambda_permission.s3_reports["mailer"]
  id = "peach-report-mailer/peach-reports-ReportMailerPermission-aSuKOoRhE3Hs"
}

import {
  to = aws_lambda_permission.s3_reports["dispatcher"]
  id = "peach-report-dispatcher/peach-reports-ReportDispatcherPermission-u7xveq0rugIY"
}
