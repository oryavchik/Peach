#!/usr/bin/env bash
# Update only the reports stack, preserving the API, database and frontend.
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
STACK="${REPORTS_STACK_NAME:-${PROJECT_NAME}-reports}"
: "${REPORT_IMAGE_URI:?Set REPORT_IMAGE_URI to the built backend ECR image URI}"
: "${REPORT_SENDER:?Set REPORT_SENDER to your SES-verified sender}"
: "${REPORT_RECIPIENTS:?Set REPORT_RECIPIENTS to comma-separated verified addresses}"
CHANGE_SET="reports-$(date -u +%Y%m%d%H%M%S)"
aws cloudformation validate-template --template-body "file://${ROOT}/infra/reports.yml" >/dev/null
aws cloudformation create-change-set \
  --stack-name "${STACK}" --change-set-name "${CHANGE_SET}" --change-set-type UPDATE \
  --template-body "file://${ROOT}/infra/reports.yml" --capabilities CAPABILITY_IAM \
  --tags "Key=PROJECT_NAME,Value=${PROJECT_NAME}" \
  --parameters \
    "ParameterKey=ProjectName,ParameterValue=${PROJECT_NAME}" \
    "ParameterKey=ReportImageUri,ParameterValue=${REPORT_IMAGE_URI}" \
    "ParameterKey=ReportSender,ParameterValue=${REPORT_SENDER}" \
    "ParameterKey=ReportRecipients,ParameterValue=\"${REPORT_RECIPIENTS}\"" \
    "ParameterKey=SenderDomain,ParameterValue=${REPORT_SENDER_DOMAIN:-}" >/dev/null
if ! aws cloudformation wait change-set-create-complete --stack-name "${STACK}" --change-set-name "${CHANGE_SET}"; then
  reason="$(aws cloudformation describe-change-set --stack-name "${STACK}" \
    --change-set-name "${CHANGE_SET}" --query StatusReason --output text)"
  if [[ "${reason}" == *"didn't contain changes"* || "${reason}" == *"No updates are to be performed"* ]]; then
    echo 'Reports stack is already up to date.'
    exit 0
  fi
  printf '%s\n' "${reason}" >&2
  exit 1
fi
# Replacing buckets/queues would risk existing reports/messages: fail before execution.
STACK="${STACK}" CHANGE_SET="${CHANGE_SET}" python3 - <<'PY'
import json, os, subprocess
result = json.loads(subprocess.check_output([
    "aws", "cloudformation", "describe-change-set", "--stack-name", os.environ["STACK"],
    "--change-set-name", os.environ["CHANGE_SET"], "--output", "json",
]))
for entry in result["Changes"]:
    change = entry["ResourceChange"]
    print(change["Action"], change["LogicalResourceId"], "replacement=" + str(change.get("Replacement", "none")))
    # Queue visibility/tag changes preserve its ARN; CFN still marks the
    # dependent polling mapping Conditional. The mapping stores no messages.
    mapping_reference_only = (
        change["ResourceType"] == "AWS::Lambda::EventSourceMapping"
        and change.get("Replacement") == "Conditional"
        and all(
            detail["Target"].get("Attribute") == "Tags"
            or (detail.get("Evaluation") == "Dynamic"
                and detail.get("CausingEntity") == "ReportsQueue.Arn")
            for detail in change.get("Details", [])
        )
    )
    if (change.get("Replacement") in {"True", "Conditional"} and not mapping_reference_only
            or change["Action"] == "Remove"):
        raise SystemExit("Stopped: review resource replacement/removal manually")
PY
printf 'Stack: %s\nChange set: %s\n' "${STACK}" "${CHANGE_SET}"
if [[ "${1:-}" == "--prepare" ]]; then
  echo 'Prepared only; no running resources changed.'
  exit 0
fi
aws cloudformation execute-change-set --stack-name "${STACK}" --change-set-name "${CHANGE_SET}"
aws cloudformation wait stack-update-complete --stack-name "${STACK}"
echo 'Reports deployment complete.'
