# Source after loading .env. Enabled only after the reviewed ownership handoff.
if [[ "${TF_MANAGED_FEATURES:-false}" == "true" ]]; then
  TF_BIN="${TERRAFORM:-terraform}"
  COGNITO_USER_POOL_ID="$("$TF_BIN" -chdir="${ROOT}/infra" output -raw cognito_user_pool_id)"
  COGNITO_CLIENT_ID="$("$TF_BIN" -chdir="${ROOT}/infra" output -raw cognito_client_id)"
  TF_COGNITO_URL="$("$TF_BIN" -chdir="${ROOT}/infra" output -raw cognito_domain)"
  export COGNITO_DOMAIN="${TF_COGNITO_URL#https://}"
  AGENDA_PARSER_URL="$("$TF_BIN" -chdir="${ROOT}/infra" output -raw parser_url)"
  PARSER_ENABLED="$("$TF_BIN" -chdir="${ROOT}/infra" output -raw parser_enabled)"
  export COGNITO_USER_POOL_ID COGNITO_CLIENT_ID AGENDA_PARSER_URL PARSER_ENABLED
fi
