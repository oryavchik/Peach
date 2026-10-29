#!/usr/bin/env bash
# Infrastructure changes are planned here and reviewed/applied only in HCP.
# See docs/TERRAFORM_MIGRATION.md before handing off existing CFN resources.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec make -C "$ROOT" infra-plan
