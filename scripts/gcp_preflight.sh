#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   PROJECT_ID=daily-digest-app-495805 REGION=asia-southeast1 ./scripts/gcp_preflight.sh

PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-asia-southeast1}"
REPOSITORY="${REPOSITORY:-digest}"
BILLING_ACCOUNT_ID="${BILLING_ACCOUNT_ID:-}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "[ERROR] PROJECT_ID is required."
  echo "Example: PROJECT_ID=daily-digest-app-495805 ./scripts/gcp_preflight.sh"
  exit 1
fi

if command -v gcloud >/dev/null 2>&1; then
  GCLOUD_BIN="$(command -v gcloud)"
elif [[ -x "/opt/homebrew/share/google-cloud-sdk/bin/gcloud" ]]; then
  GCLOUD_BIN="/opt/homebrew/share/google-cloud-sdk/bin/gcloud"
else
  echo "[ERROR] gcloud not found on PATH and not found at /opt/homebrew/share/google-cloud-sdk/bin/gcloud"
  exit 1
fi

if [[ -z "${CLOUDSDK_CONFIG:-}" ]]; then
  export CLOUDSDK_CONFIG="$PWD/.gcloud-config"
fi

echo "[INFO] Using gcloud: $GCLOUD_BIN"
echo "[INFO] CLOUDSDK_CONFIG: $CLOUDSDK_CONFIG"

"$GCLOUD_BIN" --version >/dev/null

# Auth/account check
ACCOUNT="$($GCLOUD_BIN auth list --filter=status:ACTIVE --format='value(account)' || true)"
if [[ -z "$ACCOUNT" ]]; then
  echo "[ERROR] No active gcloud account. Run: $GCLOUD_BIN auth login --no-launch-browser"
  exit 1
fi

echo "[OK] Active account: $ACCOUNT"

# Project check
"$GCLOUD_BIN" config set project "$PROJECT_ID" >/dev/null
ACTIVE_PROJECT="$($GCLOUD_BIN config get-value project 2>/dev/null || true)"
if [[ "$ACTIVE_PROJECT" != "$PROJECT_ID" ]]; then
  echo "[ERROR] Failed to set active project to $PROJECT_ID"
  exit 1
fi

echo "[OK] Active project: $ACTIVE_PROJECT"

# Billing check. Service enablement fails without an attached billing account.
# Prefer stable command; fall back to beta only if needed for older SDK variants.
BILLING_ENABLED="$($GCLOUD_BIN billing projects describe "$PROJECT_ID" --format='value(billingEnabled)' 2>/dev/null || true)"
if [[ -z "$BILLING_ENABLED" ]]; then
  BILLING_ENABLED="$($GCLOUD_BIN beta billing projects describe "$PROJECT_ID" --format='value(billingEnabled)' 2>/dev/null || true)"
fi
if [[ "$BILLING_ENABLED" != "True" ]]; then
  echo "[WARN] Billing is not enabled on project: $PROJECT_ID"
  if [[ -n "$BILLING_ACCOUNT_ID" ]]; then
    echo "[INFO] Linking billing account: $BILLING_ACCOUNT_ID"
    "$GCLOUD_BIN" billing projects link "$PROJECT_ID" --billing-account "$BILLING_ACCOUNT_ID" >/dev/null
    BILLING_ENABLED="$($GCLOUD_BIN billing projects describe "$PROJECT_ID" --format='value(billingEnabled)' 2>/dev/null || true)"
    if [[ -z "$BILLING_ENABLED" ]]; then
      BILLING_ENABLED="$($GCLOUD_BIN beta billing projects describe "$PROJECT_ID" --format='value(billingEnabled)' 2>/dev/null || true)"
    fi
  fi
fi

if [[ "$BILLING_ENABLED" != "True" ]]; then
  echo "[ERROR] Billing remains disabled for project $PROJECT_ID."
  echo "        Link billing first, then re-run preflight."
  echo "        Optional automation: BILLING_ACCOUNT_ID=XXXX-XXXX-XXXX ./scripts/gcp_preflight.sh"
  exit 1
fi

echo "[OK] Billing enabled"

# Required APIs for this workflow
REQUIRED_APIS=(
  run.googleapis.com
  cloudscheduler.googleapis.com
  artifactregistry.googleapis.com
  secretmanager.googleapis.com
)

MISSING_APIS=()
for api in "${REQUIRED_APIS[@]}"; do
  if ! "$GCLOUD_BIN" services list --enabled --filter="name:$api" --format='value(name)' | grep -q "^$api$"; then
    MISSING_APIS+=("$api")
  fi
done

if (( ${#MISSING_APIS[@]} > 0 )); then
  echo "[WARN] Missing enabled APIs: ${MISSING_APIS[*]}"
  echo "[INFO] Enabling missing APIs..."
  "$GCLOUD_BIN" services enable "${MISSING_APIS[@]}"
fi

echo "[OK] Required APIs enabled"

# Artifact Registry repo check
if "$GCLOUD_BIN" artifacts repositories describe "$REPOSITORY" --location "$REGION" >/dev/null 2>&1; then
  echo "[OK] Artifact Registry repo exists: $REPOSITORY ($REGION)"
else
  echo "[WARN] Artifact Registry repo '$REPOSITORY' not found in $REGION"
  echo "[INFO] It will be created during deploy script."
fi

# Secret checks (warn-only to keep preflight informative)
REQUIRED_SECRETS=(deepseek-key newsapi-key github-token)
MISSING_SECRETS=()
for sec in "${REQUIRED_SECRETS[@]}"; do
  if ! "$GCLOUD_BIN" secrets describe "$sec" >/dev/null 2>&1; then
    MISSING_SECRETS+=("$sec")
  fi
done

if (( ${#MISSING_SECRETS[@]} > 0 )); then
  echo "[WARN] Missing secrets: ${MISSING_SECRETS[*]}"
  echo "[INFO] Create them before deploy, e.g.:"
  echo "  echo -n 'YOUR_VALUE' | $GCLOUD_BIN secrets create NAME --data-file=-"
  echo "  echo -n 'YOUR_VALUE' | $GCLOUD_BIN secrets versions add NAME --data-file=-"
else
  echo "[OK] Required secrets found"
fi

echo "[SUCCESS] Preflight completed"
