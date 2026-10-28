#!/usr/bin/env bash
# Only the free model router; no weights, cloud deployment or paid fallback.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$ROOT/.env" ]]; then
  set -a
  source "$ROOT/.env"
  set +a
fi
export PARSER_PROVIDER=openrouter_free
export PARSER_ENABLED=true
UV_BIN="${UV:-${HOME}/.local/bin/uv}"
case "${1:-}" in
  server)
    : "${OPENROUTER_API_KEY:?Add OPENROUTER_API_KEY to the root .env}"
    cd "$ROOT/backend"
    exec "$UV_BIN" run uvicorn app.ai.free_server:app --host 127.0.0.1 --port 8001
    ;;
  parse|hello)
    : "${OPENROUTER_API_KEY:?Add OPENROUTER_API_KEY to the root .env}"
    cd "$ROOT/backend"
    exec "$UV_BIN" run python -m app.ai.cli "$1"
    ;;
  evaluate)
    : "${OPENROUTER_API_KEY:?Add OPENROUTER_API_KEY to the root .env}"
    cd "$ROOT/backend"
    exec "$UV_BIN" run python -m app.ai.evaluate
    ;;
  frontend)
    export NEXT_PUBLIC_AGENDA_PARSER_ENABLED=true
    export NEXT_PUBLIC_AGENDA_PARSER_URL=/agenda-parser
    export LOCAL_API_PROXY_URL="${BACKEND_URL:?Missing BACKEND_URL in .env}"
    export NEXT_PUBLIC_API_URL=/
    export INTERNAL_API_URL="$LOCAL_API_PROXY_URL"
    export NEXT_PUBLIC_COGNITO_REGION="${COGNITO_REGION:-us-east-1}"
    export NEXT_PUBLIC_COGNITO_USER_POOL_ID="${COGNITO_USER_POOL_ID:?}"
    export NEXT_PUBLIC_COGNITO_CLIENT_ID="${COGNITO_CLIENT_ID:?}"
    export NEXT_PUBLIC_COGNITO_DOMAIN="${COGNITO_DOMAIN:?}"
    export NEXT_PUBLIC_COGNITO_REDIRECT_URI=http://localhost:3000/auth/callback
    cd "$ROOT/frontend"
    exec pnpm dev --hostname localhost
    ;;
  *)
    echo 'Usage: bash scripts/free-ai.sh server|frontend|parse|hello|evaluate' >&2
    exit 2
    ;;
esac
