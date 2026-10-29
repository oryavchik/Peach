resource "aws_iam_role" "parser" {
  name               = var.role_names.parser
  assume_role_policy = local.lambda_trust
  tags               = local.tags
}

resource "aws_iam_role_policy_attachment" "parser_logs" {
  role       = aws_iam_role.parser.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "parser_inference" {
  name = "InferenceOnly"
  role = aws_iam_role.parser.id
  policy = jsonencode({
    Version = "2012-10-17", Statement = [{
      Effect = var.parser_enabled ? "Allow" : "Deny"
      Action = "bedrock-mantle:CreateInference", Resource = "*"
      }
    ]
    }
  )
}

resource "aws_cloudwatch_log_group" "parser" {
  name              = "/aws/lambda/${var.project_name}-agenda-parser"
  retention_in_days = 14
  tags              = local.tags
  lifecycle {
    prevent_destroy = true
  }

}

resource "aws_lambda_function" "parser" {
  function_name = "${var.project_name}-agenda-parser"
  package_type  = "Image"
  image_uri     = var.parser_image_uri
  architectures = ["arm64"]
  image_config {
    command = ["app.ai.agenda_lambda.handler"]
  }

  role        = aws_iam_role.parser.arn
  timeout     = 30
  memory_size = 512
  environment {
    variables = {
      APP_ENV              = "production"
      COGNITO_REGION       = var.region
      COGNITO_USER_POOL_ID = aws_cognito_user_pool.main.id
      COGNITO_CLIENT_ID    = aws_cognito_user_pool_client.web.id
      PARSER_ENABLED       = tostring(var.parser_enabled)
      PARSER_MODEL         = var.parser_model
      PARSER_INPUT_PRICE   = tostring(var.parser_input_price)
      PARSER_OUTPUT_PRICE  = tostring(var.parser_output_price)
    }
  }

  tags       = local.tags
  depends_on = [aws_cloudwatch_log_group.parser, aws_iam_role_policy_attachment.parser_logs]
  lifecycle {
    prevent_destroy = true
    ignore_changes  = [image_uri]
  }

}

resource "aws_lambda_function_url" "parser" {
  function_name      = aws_lambda_function.parser.function_name
  authorization_type = "NONE"
  cors {
    allow_origins = [var.frontend_url]
    allow_methods = ["POST"]
    allow_headers = ["authorization", "content-type"]
    max_age       = 300
  }

}

resource "aws_lambda_permission" "parser_url" {
  statement_id           = var.permission_statement_ids.parser_url
  function_name          = aws_lambda_function.parser.function_name
  action                 = "lambda:InvokeFunctionUrl"
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "parser_invoke" {
  statement_id             = var.permission_statement_ids.parser_invoke
  function_name            = aws_lambda_function.parser.function_name
  action                   = "lambda:InvokeFunction"
  principal                = "*"
  invoked_via_function_url = true
}

resource "aws_budgets_budget" "ai" {
  account_id   = local.account_id
  name         = "${var.project_name}-ai-lab-monthly-5usd"
  budget_type  = "COST"
  limit_amount = "5"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_email]
  }

  tags = local.tags
  lifecycle {
    prevent_destroy = true
  }

}

