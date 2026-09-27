#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../infra/terraform"

if [ -z "${GEMINI_API_KEY:-}" ]; then
  echo "Set GEMINI_API_KEY before running this script."
  exit 1
fi

terraform init
terraform apply -var="gemini_api_key=$GEMINI_API_KEY" "$@"

echo
echo "Deployment complete. Outputs:"
terraform output
