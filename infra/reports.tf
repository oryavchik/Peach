locals {
  report_handlers = {
    builder = {
      name = "peach-report-builder", command = "app.reports.lambda_handler.handler", timeout = 60, memory = 512
    }

    dispatcher = {
      name = "peach-report-dispatcher", command = "app.reports.dispatcher.handler", timeout = 30, memory = 256
    }

    mailer = {
      name = "peach-report-mailer", command = "app.reports.mailer.handler", timeout = 30, memory = 256
    }

  }

  report_managed_policies = {
    builder    = "AWSLambdaVPCAccessExecutionRole"
    dispatcher = "AWSLambdaBasicExecutionRole"
    mailer     = "AWSLambdaBasicExecutionRole"
  }

  report_policy_names = {
    builder = "ReportsAccess", dispatcher = "RequestDispatch", mailer = "MailerAccess", scheduler = "SendReportsMessage"
  }

  report_statements = {
    builder = [
      {
        Effect = "Allow", Action = ["s3:PutObject"], Resource = "${aws_s3_bucket.reports.arn}/reports/*"
      }
      ,
      {
        Effect = "Allow", Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"], Resource = aws_sqs_queue.reports.arn
      }

    ]
    dispatcher = [
      {
        Effect = "Allow", Action = ["s3:GetObject"], Resource = "${aws_s3_bucket.reports.arn}/requests/*"
      }
      ,
      {
        Effect = "Allow", Action = ["sqs:SendMessage"], Resource = aws_sqs_queue.reports.arn
      }

    ]
    mailer = [
      {
        Effect = "Allow", Action = ["s3:GetObject"], Resource = "${aws_s3_bucket.reports.arn}/reports/*"
      }
      ,
      {
        Effect = "Allow", Action = ["ses:SendEmail", "ses:SendRawEmail"], Resource = "*"
      }

    ]
    scheduler = [{
      Effect = "Allow", Action = ["sqs:SendMessage"], Resource = aws_sqs_queue.reports.arn
      }
    ]
  }

}

resource "aws_sesv2_email_identity" "sender_domain" {
  count          = var.sender_domain == "" ? 0 : 1
  email_identity = var.sender_domain
  lifecycle {
    prevent_destroy = true
  }

}

resource "aws_s3_bucket" "reports" {
  bucket        = local.reports_bucket_name
  force_destroy = false
  tags          = local.tags
  lifecycle {
    prevent_destroy = true
  }

}

resource "aws_s3_bucket_public_access_block" "reports" {
  bucket                  = aws_s3_bucket.reports.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id
  rule {
    id     = "DeleteOldReports"
    status = "Enabled"
    filter {
      prefix = "reports/"
    }

    expiration {
      days = 90
    }

  }

  rule {
    id     = "DeleteRequests"
    status = "Enabled"
    filter {
      prefix = "requests/"
    }

    expiration {
      days = 7
    }

  }

}

resource "aws_sqs_queue" "dlq" {
  name             = "peach-reports-dlq"
  max_message_size = 1048576
  tags             = local.tags
  lifecycle {
    prevent_destroy = true
  }

}

resource "aws_sqs_queue" "reports" {
  name                       = "peach-reports-queue"
  max_message_size           = 1048576
  visibility_timeout_seconds = 360
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn, maxReceiveCount = 3
    }
  )
  tags = local.tags
  lifecycle {
    prevent_destroy = true
  }

}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = var.route_table_ids
  tags              = local.tags
  lifecycle {
    prevent_destroy = true
  }

}

resource "aws_iam_role" "reports" {
  for_each = toset(["builder", "dispatcher", "mailer", "scheduler"])
  name     = var.role_names[each.key]
  assume_role_policy = each.key == "scheduler" ? jsonencode({
    Version = "2012-10-17", Statement = [{
      Effect = "Allow", Action = "sts:AssumeRole", Principal = {
        Service = "scheduler.amazonaws.com"
      }
      }
    ]
    }
  ) : local.lambda_trust
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "reports" {
  for_each   = local.report_managed_policies
  role       = aws_iam_role.reports[each.key].name
  policy_arn = "arn:${local.partition}:iam::aws:policy/service-role/${each.value}"
}

resource "aws_iam_role_policy" "reports" {
  for_each = local.report_policy_names
  name     = each.value
  role     = aws_iam_role.reports[each.key].id
  policy = jsonencode({
    Version = "2012-10-17", Statement = local.report_statements[each.key]
    }
  )
}

resource "aws_iam_role_policy" "api_report_requests" {
  name = "PeachReportRequests"
  role = var.api_execution_role_name
  policy = jsonencode({
    Version = "2012-10-17", Statement = [{
      Effect = "Allow", Action = "s3:PutObject", Resource = "${aws_s3_bucket.reports.arn}/requests/*"
      }
    ]
    }
  )
}

resource "aws_lambda_function" "reports" {
  for_each      = local.report_handlers
  function_name = each.value.name
  package_type  = "Image"
  image_uri     = var.report_image_uri
  image_config {
    command = [each.value.command]
  }

  architectures = ["arm64"]
  role          = aws_iam_role.reports[each.key].arn
  timeout       = each.value.timeout
  memory_size   = each.value.memory
  dynamic "vpc_config" {
    for_each = each.key == "builder" ? [1] : []
    content {
      security_group_ids = var.builder_security_group_ids
      subnet_ids         = var.builder_subnet_ids
    }

  }

  environment {
    variables = each.key == "builder" ? {
      APP_ENV = "production", DB_POOLING = "false", DATABASE_URL = var.database_url, REPORTS_BUCKET = aws_s3_bucket.reports.id
      } : each.key == "dispatcher" ? {
      REPORTS_BUCKET = aws_s3_bucket.reports.id, REPORT_QUEUE_URL = aws_sqs_queue.reports.url
      } : {
      REPORT_SENDER = var.report_sender, REPORT_RECIPIENTS = join(",", var.report_recipients)
    }

  }

  tags       = local.tags
  depends_on = [aws_vpc_endpoint.s3, aws_iam_role_policy_attachment.reports, aws_iam_role_policy.reports]
  lifecycle {
    prevent_destroy = true
    ignore_changes  = [image_uri]
  }

}

resource "aws_lambda_permission" "s3_reports" {
  for_each       = toset(["mailer", "dispatcher"])
  statement_id   = var.permission_statement_ids[each.key]
  function_name  = aws_lambda_function.reports[each.key].function_name
  action         = "lambda:InvokeFunction"
  principal      = "s3.amazonaws.com"
  source_account = local.account_id
  source_arn     = aws_s3_bucket.reports.arn
}

resource "aws_s3_bucket_notification" "reports" {
  bucket = aws_s3_bucket.reports.id
  lambda_function {
    lambda_function_arn = aws_lambda_function.reports["mailer"].arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "reports/"
    filter_suffix       = ".csv"
  }

  lambda_function {
    lambda_function_arn = aws_lambda_function.reports["dispatcher"].arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "requests/"
    filter_suffix       = ".json"
  }

  depends_on = [aws_lambda_permission.s3_reports]
}

resource "aws_lambda_event_source_mapping" "reports" {
  tags             = local.tags
  event_source_arn = aws_sqs_queue.reports.arn
  function_name    = aws_lambda_function.reports["builder"].arn
  batch_size       = 1
  enabled          = true
}

resource "aws_scheduler_schedule" "weekly" {
  name                         = "peach-weekly-reports"
  group_name                   = "default"
  schedule_expression          = "cron(0 7 ? * MON *)"
  schedule_expression_timezone = "Europe/Kyiv"
  flexible_time_window {
    mode = "OFF"
  }

  state = "ENABLED"
  target {
    arn      = aws_sqs_queue.reports.arn
    role_arn = aws_iam_role.reports["scheduler"].arn
    # Preserve the existing string: Scheduler compares JSON input bytewise.
    input = "{\"week\":null,\"source\":\"schedule\"}"
  }

}

