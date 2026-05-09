#!/usr/bin/env bash
set -euo pipefail

# Create/update required GCP Secret Manager secrets from local .env values.
# Usage:
#   PROJECT_ID=daily-digest-app-495805 ./scripts/setup_gcp_secrets.sh
#   PROJECT_ID=... ENV_FILE=.env ./scripts/setup_gcp_secrets.sh

PROJECT_ID="${PROJECT_ID:-}"
ENV_FILE="${ENV_FILE:-.env}"
GOOGLE_SERVICE_ACCOUNT_JSON_FILE="${GOOGLE_SERVICE_ACCOUNT_JSON_FILE:-}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "[ERROR] PROJECT_ID is required"
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[ERROR] ENV_FILE not found: $ENV_FILE"
  exit 1
fi

if command -v gcloud >/dev/null 2>&1; then
  GCLOUD_BIN="$(command -v gcloud)"
elif [[ -x "/opt/homebrew/share/google-cloud-sdk/bin/gcloud" ]]; then
  GCLOUD_BIN="/opt/homebrew/share/google-cloud-sdk/bin/gcloud"
else
  echo "[ERROR] gcloud not found"
  exit 1
fi

if [[ -z "${CLOUDSDK_CONFIG:-}" ]]; then
  export CLOUDSDK_CONFIG="$PWD/.gcloud-config"
fi

get_env_value() {
  local key="$1"
  local line
  # Read last matching non-comment key=value line.
  line="$(grep -E "^[[:space:]]*${key}=" "$ENV_FILE" | grep -v '^[[:space:]]*#' | tail -n 1 || true)"
  if [[ -z "$line" ]]; then
    echo ""
    return 0
  fi

  # Keep everything after first '=' exactly as value.
  local value="${line#*=}"
  # Trim surrounding spaces only.
  value="$(printf '%s' "$value" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  printf '%s' "$value"
}

"$GCLOUD_BIN" config set project "$PROJECT_ID" >/dev/null

upsert_secret() {
  local secret_name="$1"
  local value="$2"

  if [[ -z "$value" ]]; then
    echo "[WARN] Skip empty value for secret: $secret_name"
    return 0
  fi

  if ! "$GCLOUD_BIN" secrets describe "$secret_name" >/dev/null 2>&1; then
    # Create secret container once.
    echo -n "$value" | "$GCLOUD_BIN" secrets create "$secret_name" --replication-policy=automatic --data-file=- >/dev/null
    echo "[OK] Created secret: $secret_name"
  else
    # Add a new version only.
    echo -n "$value" | "$GCLOUD_BIN" secrets versions add "$secret_name" --data-file=- >/dev/null
    echo "[OK] Updated secret version: $secret_name"
  fi
}

upsert_secret "deepseek-key" "$(get_env_value DEEPSEEK_API_KEY)"
upsert_secret "newsapi-key" "$(get_env_value NEWSAPI_KEY)"
upsert_secret "github-token" "$(get_env_value GITHUB_TOKEN)"

GOOGLE_SA_JSON_VALUE="$(get_env_value GOOGLE_SERVICE_ACCOUNT_JSON)"
if [[ -z "$GOOGLE_SA_JSON_VALUE" && -n "$GOOGLE_SERVICE_ACCOUNT_JSON_FILE" ]]; then
  if [[ ! -f "$GOOGLE_SERVICE_ACCOUNT_JSON_FILE" ]]; then
    echo "[ERROR] GOOGLE_SERVICE_ACCOUNT_JSON_FILE not found: $GOOGLE_SERVICE_ACCOUNT_JSON_FILE"
    exit 1
  fi
  GOOGLE_SA_JSON_VALUE="$(cat "$GOOGLE_SERVICE_ACCOUNT_JSON_FILE")"
fi
upsert_secret "google-service-account-json" "$GOOGLE_SA_JSON_VALUE"

echo "[SUCCESS] Secret bootstrap complete"
