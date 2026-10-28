#!/usr/bin/env bash
# Build the original Next.js interface for the free Worker/D1 backend.
# No .env secrets or AWS configuration are needed in the browser build.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/frontend"
NEXT_OUTPUT=export \
NEXT_PUBLIC_AUTH_MODE=cloudflare \
NEXT_PUBLIC_API_URL=/ \
NEXT_PUBLIC_AGENDA_PARSER_ENABLED=true \
NEXT_PUBLIC_AGENDA_PARSER_URL=/api/parse \
pnpm build
