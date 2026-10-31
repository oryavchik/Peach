# PREPARED ONLY. Separate root: never add to the live Peach infra workspace.
terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers { aws = { source = "hashicorp/aws", version = "~> 6.0" } }
}
variable "account_id" { type = string }
variable "alert_email" { type = string }
variable "region" { default = "us-east-1" }
variable "name" { default = "peach-lab8" }
provider "aws" {
  region              = var.region
  allowed_account_ids = [var.account_id]
  default_tags { tags = { Project = var.name, Purpose = "lab8-temporary" } }
}
locals {
  bucket = "${var.name}-${var.account_id}-${var.region}"
}
resource "aws_s3_bucket" "data" { bucket = local.bucket }
resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    id     = "lab-retention"
    status = "Enabled"
    filter { prefix = "" }
    expiration { days = 7 }
  }
}
resource "aws_kinesis_stream" "payments" {
  name             = var.name
  retention_period = 24
  stream_mode_details { stream_mode = "ON_DEMAND" }
}
resource "aws_iam_role" "firehose" {
  name               = "${var.name}-firehose"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "firehose.amazonaws.com" } }] })
}
resource "aws_iam_role_policy" "firehose" {
  role = aws_iam_role.firehose.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["kinesis:DescribeStream", "kinesis:GetShardIterator", "kinesis:GetRecords", "kinesis:ListShards"], Resource = aws_kinesis_stream.payments.arn },
    { Effect = "Allow", Action = ["s3:GetBucketLocation", "s3:ListBucket", "s3:ListBucketMultipartUploads"], Resource = aws_s3_bucket.data.arn },
    { Effect = "Allow", Action = ["s3:AbortMultipartUpload", "s3:GetObject", "s3:PutObject"], Resource = "${aws_s3_bucket.data.arn}/*" }
  ] })
}
resource "aws_kinesis_firehose_delivery_stream" "payments" {
  name        = var.name
  destination = "extended_s3"
  kinesis_source_configuration {
    kinesis_stream_arn = aws_kinesis_stream.payments.arn
    role_arn           = aws_iam_role.firehose.arn
  }
  extended_s3_configuration {
    role_arn            = aws_iam_role.firehose.arn
    bucket_arn          = aws_s3_bucket.data.arn
    prefix              = "payments-stream/dt=!{timestamp:yyyy-MM-dd}/"
    error_output_prefix = "errors/!{firehose:error-output-type}/"
    buffering_interval  = 60
    buffering_size      = 1
    compression_format  = "GZIP"
  }
  depends_on = [aws_iam_role_policy.firehose]
}
resource "aws_glue_catalog_database" "payments" { name = replace(var.name, "-", "_") }
resource "aws_iam_role" "crawler" {
  name               = "${var.name}-crawler"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "glue.amazonaws.com" } }] })
}
resource "aws_iam_role_policy_attachment" "crawler" {
  role       = aws_iam_role.crawler.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}
resource "aws_iam_role_policy" "crawler_data" {
  role = aws_iam_role.crawler.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["s3:ListBucket"], Resource = aws_s3_bucket.data.arn },
    { Effect = "Allow", Action = ["s3:GetObject"], Resource = "${aws_s3_bucket.data.arn}/*" }
  ] })
}
resource "aws_glue_crawler" "stream" {
  name          = "${var.name}-stream"
  database_name = aws_glue_catalog_database.payments.name
  role          = aws_iam_role.crawler.arn
  table_prefix  = "stream_"
  s3_target { path = "s3://${aws_s3_bucket.data.id}/payments-stream/" }
  depends_on = [aws_iam_role_policy_attachment.crawler, aws_iam_role_policy.crawler_data]
}
resource "aws_sns_topic" "alerts" { name = "${var.name}-alerts" }
resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}
resource "aws_iam_role" "lambda" {
  name               = "${var.name}-alert"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "lambda.amazonaws.com" } }] })
}
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
resource "aws_iam_role_policy" "lambda" {
  role = aws_iam_role.lambda.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["kinesis:DescribeStream", "kinesis:DescribeStreamSummary", "kinesis:GetRecords", "kinesis:GetShardIterator", "kinesis:ListShards", "kinesis:ListStreams"], Resource = aws_kinesis_stream.payments.arn },
    { Effect = "Allow", Action = ["sns:Publish"], Resource = aws_sns_topic.alerts.arn }
  ] })
}
resource "aws_lambda_function" "alert" {
  function_name    = "${var.name}-alert"
  role             = aws_iam_role.lambda.arn
  filename         = "${path.module}/alert.zip"
  source_code_hash = filebase64sha256("${path.module}/alert.zip")
  handler          = "alert.handler"
  runtime          = "python3.13"
  timeout          = 30
  environment { variables = { ALERT_TOPIC_ARN = aws_sns_topic.alerts.arn } }
  depends_on = [aws_iam_role_policy.lambda, aws_iam_role_policy_attachment.lambda_logs]
}
resource "aws_lambda_event_source_mapping" "payments" {
  event_source_arn           = aws_kinesis_stream.payments.arn
  function_name              = aws_lambda_function.alert.arn
  starting_position          = "TRIM_HORIZON"
  batch_size                 = 100
  tumbling_window_in_seconds = 60
  maximum_retry_attempts     = 2
}
resource "aws_athena_workgroup" "payments" {
  name = var.name
  configuration {
    enforce_workgroup_configuration = true
    bytes_scanned_cutoff_per_query  = 2000000000
    result_configuration { output_location = "s3://${aws_s3_bucket.data.id}/athena-results/" }
  }
}
output "stream_name" { value = aws_kinesis_stream.payments.name }
output "bucket_name" { value = aws_s3_bucket.data.id }
output "database" { value = aws_glue_catalog_database.payments.name }
output "crawler" { value = aws_glue_crawler.stream.name }
