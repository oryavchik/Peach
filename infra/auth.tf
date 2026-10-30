resource "aws_cognito_user_pool" "main" {
  name                     = "${var.project_name}-users"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  user_pool_tier           = "ESSENTIALS"
  admin_create_user_config {
    allow_admin_create_user_only = false
  }

  # Adopt the existing immutable username case-sensitivity setting.
  # Provider 6.71 computes username_configuration from AWS when omitted;
  # imposing false during import can force replacement of an existing pool.

  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_uppercase = true
    require_numbers   = true
    require_symbols   = false
  }

  schema {
    name                = "email"
    attribute_data_type = "String"
    mutable             = true
    required            = true
  }

  schema {
    name                = "name"
    attribute_data_type = "String"
    mutable             = true
    required            = false
  }

  tags = var.cognito_tags
  lifecycle {
    prevent_destroy = true
    # Cognito schemas are immutable; imported AWS-expanded schemas differ from CFN.
    ignore_changes = [schema]
  }

}

resource "aws_cognito_identity_provider" "google" {
  user_pool_id  = aws_cognito_user_pool.main.id
  provider_name = "Google"
  provider_type = "Google"
  provider_details = {
    client_id        = var.google_client_id
    client_secret    = var.google_client_secret
    authorize_scopes = "openid email profile"
  }

  attribute_mapping = {
    email = "email", email_verified = "email_verified", name = "name"
  }

  lifecycle {
    prevent_destroy = true
  }

}

resource "aws_cognito_user_pool_client" "web" {
  user_pool_id                         = aws_cognito_user_pool.main.id
  name                                 = "${var.project_name}-web"
  generate_secret                      = false
  supported_identity_providers         = ["COGNITO", aws_cognito_identity_provider.google.provider_name]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  callback_urls                        = ["${var.frontend_url}/auth/callback/", "http://localhost:3000/auth/callback"]
  default_redirect_uri                 = "${var.frontend_url}/auth/callback/"
  logout_urls                          = ["${var.frontend_url}/", "http://localhost:3000"]
  enable_token_revocation              = true
  prevent_user_existence_errors        = "ENABLED"
  lifecycle {
    prevent_destroy = true
  }

}

resource "aws_cognito_user_pool_domain" "main" {
  user_pool_id          = aws_cognito_user_pool.main.id
  domain                = var.cognito_domain_prefix
  managed_login_version = 2
  lifecycle {
    prevent_destroy = true
  }

}

resource "aws_cognito_managed_login_branding" "web" {
  user_pool_id                = aws_cognito_user_pool.main.id
  client_id                   = aws_cognito_user_pool_client.web.id
  use_cognito_provided_values = true
  depends_on                  = [aws_cognito_user_pool_domain.main]
}

