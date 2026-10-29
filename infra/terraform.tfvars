# Non-secret existing values only. Set sensitive values in HCP workspace variables.
project_name               = "peach"
aws_account_id             = "506126098984"
region                     = "us-east-1"
frontend_url               = "https://d2u4q6uy2ofop2.cloudfront.net"
cognito_domain_prefix      = "peach-506126098984"
cognito_tags               = {}
default_tags               = {}
parser_enabled             = false
report_image_uri           = "506126098984.dkr.ecr.us-east-1.amazonaws.com/peach-backend@sha256:a9f7c68287e247805d88a112784302020ba16cb89b05f4fa88cd23a298efe066"
parser_image_uri           = "506126098984.dkr.ecr.us-east-1.amazonaws.com/peach-backend@sha256:23b12d6cd62c79e3dddd29775d6ff05ddcfeed18375f1e2ed8c4a79bfaa32e9c"
api_execution_role_name    = "peach-backend-ExecutionRole-Wl1ccFq0TkVC"
role_names                 = { "parser" : "peach-ai-ParserRole-mdEJTPrrjCyy", "builder" : "peach-reports-ReportBuilderRole-p9u0vZcfwAEd", "dispatcher" : "peach-reports-ReportDispatcherRole-ROSvpWdj7aol", "mailer" : "peach-reports-ReportMailerRole-AybCF4Y51FJj", "scheduler" : "peach-reports-SchedulerRole-On6szH2RLPvB" }
permission_statement_ids   = { "parser_url" : "peach-ai-ParserUrlPermission-dAUemKhv75YW", "parser_invoke" : "peach-ai-ParserInvokePermission-6gmcuLalkY98", "mailer" : "peach-reports-ReportMailerPermission-aSuKOoRhE3Hs", "dispatcher" : "peach-reports-ReportDispatcherPermission-u7xveq0rugIY" }
vpc_id                     = "vpc-021d221c07e003f97"
route_table_ids            = ["rtb-05f63be5ef0440b79"]
builder_security_group_ids = ["sg-0594b79a6a59c8e79"]
builder_subnet_ids         = ["subnet-0a79e656ccbd43018", "subnet-09d34893c725a9f3d", "subnet-0926d5aeef6819cbe", "subnet-0b7a453d7e0f30ebe", "subnet-0e408246861281045"]
