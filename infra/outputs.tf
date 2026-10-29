output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.main.id
}

output "cognito_client_id" {
  value = aws_cognito_user_pool_client.web.id
}

output "cognito_domain" {
  value = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${var.region}.amazoncognito.com"
}

output "cognito_authority" {
  value = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.main.id}"
}

output "parser_url" {
  value = aws_lambda_function_url.parser.function_url
}

output "parser_enabled" { value = var.parser_enabled }

output "parser_function_name" {
  value = aws_lambda_function.parser.function_name
}

output "reports_bucket_name" {
  value = aws_s3_bucket.reports.id
}

output "reports_queue_url" {
  value = aws_sqs_queue.reports.url
}

output "reports_dlq_url" {
  value = aws_sqs_queue.dlq.url
}

output "report_function_names" {
  value = {
    for name, fn in aws_lambda_function.reports : name => fn.function_name
  }
}

output "reports_builder_name" {
  value = aws_lambda_function.reports["builder"].function_name
}

output "sender_dkim_records" {
  value = {
    for token in try(aws_sesv2_email_identity.sender_domain[0].dkim_signing_attributes[0].tokens, []) : "${token}._domainkey.${var.sender_domain}" => "${token}.dkim.amazonses.com"
  }

}

