#!/usr/bin/env bash
# Uses a prebuilt backend image; never updates the database or reports stack.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "${ROOT}/.env" ]]; then
  preset="$(export -p)"
  set -a
  source "${ROOT}/.env"
  set +a
  eval "${preset}"
fi
for var in AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN; do
  [[ -n "${!var:-}" ]] || unset "${var}"
done
export AWS_DEFAULT_REGION="${AWS_REGION:-us-east-1}"
PROJECT_NAME="${PROJECT_NAME:-peach}"
: "${AI_IMAGE_URI:?Set AI_IMAGE_URI to an immutable backend image URI}"
: "${COGNITO_USER_POOL_ID:?Missing Cognito pool}"
: "${COGNITO_CLIENT_ID:?Missing Cognito client}"
: "${AI_BUDGET_EMAIL:?Set AI_BUDGET_EMAIL for the requested monthly alert}"
# Enabling inference is a separate, explicit configuration choice. This script
# does not subscribe to models or accept Marketplace agreements.
aws cloudformation validate-template --template-body "file://${ROOT}/infra/ai.yml" >/dev/null
aws cloudformation deploy --stack-name "${PROJECT_NAME}-ai" \
  --template-file "${ROOT}/infra/ai.yml" --capabilities CAPABILITY_IAM \
  --no-fail-on-empty-changeset --tags "PROJECT_NAME=${PROJECT_NAME}" \
  --parameter-overrides \
    "ProjectName=${PROJECT_NAME}" "ImageUri=${AI_IMAGE_URI}" \
    "SiteOrigin=${AI_SITE_ORIGIN:-https://d2u4q6uy2ofop2.cloudfront.net}" \
    "CognitoPoolId=${COGNITO_USER_POOL_ID}" "CognitoClientId=${COGNITO_CLIENT_ID}" \
    "ParserEnabled=${PARSER_ENABLED:-false}" \
    "ParserModel=${PARSER_MODEL:-anthropic.claude-opus-5-5}" \
    "InputPrice=${PARSER_INPUT_PRICE:-4.4}" "OutputPrice=${PARSER_OUTPUT_PRICE:-22}" \
    "BudgetEmail=${AI_BUDGET_EMAIL}"
aws cloudformation describe-stacks --stack-name "${PROJECT_NAME}-ai" --query 'Stacks[0].Outputs' --output table
