#!/usr/bin/env bash
# Application code deployment only; no infrastructure apply or stack update.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_BIN="${TERRAFORM:-terraform}"
: "${IMAGE_URI:?Supply an already built immutable ECR image digest}"
[[ "$IMAGE_URI" == *@sha256:* ]] || { echo 'Use an immutable image digest.' >&2; exit 1; }
case "${1:-}" in
  reports)
    NAMES="$("$TF_BIN" -chdir="$ROOT/infra" output -json report_function_names)"
    for component in builder dispatcher mailer; do
      function_name="$(printf '%s' "$NAMES" | python3 -c 'import json,sys; print(json.load(sys.stdin)[sys.argv[1]])' "$component")"
      aws lambda update-function-code --function-name "$function_name" --image-uri "$IMAGE_URI" --query FunctionName --output text
      aws lambda wait function-updated --function-name "$function_name"
    done
    ;;
  parser)
    function_name="$("$TF_BIN" -chdir="$ROOT/infra" output -raw parser_function_name)"
    aws lambda update-function-code --function-name "$function_name" --image-uri "$IMAGE_URI" --query FunctionName --output text
    aws lambda wait function-updated --function-name "$function_name"
    ;;
  *) echo 'Usage: IMAGE_URI=... bash scripts/deploy-feature-code.sh reports|parser' >&2; exit 2 ;;
esac
