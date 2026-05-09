#!/usr/bin/env bash
set -euo pipefail

# End-to-end release runner for Cloud Run Jobs deployment.
#
# Stages:
#   1) Preflight
#   2) Secret bootstrap
#   3) Deploy/update Cloud Run Job + Scheduler
#   4) Post-deploy health check
#
# Usage example:
#   PROJECT_ID=daily-digest-app-495805 REGION=asia-southeast1 \
#   TIMEZONE=Asia/Hong_Kong SCHEDULE="0 7 * * *" \
#   ./scripts/gcp_release_run.sh
#
# Optional toggles:
#   DRY_RUN=true                # print commands only
#   RUN_PREFLIGHT=true          # default true
#   RUN_SECRETS=true            # default true
#   RUN_DEPLOY=true             # default true
#   RUN_HEALTH=true             # default true
#   RUN_VALIDATE_DRIVE=true     # default true
#   SMOKE_EXECUTE=true          # passed to deploy script (default false)
#   MAX_EXECUTION_AGE_HOURS=30  # passed to health check

PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-asia-southeast1}"
TIMEZONE="${TIMEZONE:-Asia/Hong_Kong}"
SCHEDULE="${SCHEDULE:-0 7 * * *}"
BILLING_ACCOUNT_ID="${BILLING_ACCOUNT_ID:-}"

RUN_PREFLIGHT="${RUN_PREFLIGHT:-true}"
RUN_SECRETS="${RUN_SECRETS:-true}"
RUN_DEPLOY="${RUN_DEPLOY:-true}"
RUN_HEALTH="${RUN_HEALTH:-true}"
RUN_VALIDATE_DRIVE="${RUN_VALIDATE_DRIVE:-true}"

DRY_RUN="${DRY_RUN:-false}"
SMOKE_EXECUTE="${SMOKE_EXECUTE:-false}"
MAX_EXECUTION_AGE_HOURS="${MAX_EXECUTION_AGE_HOURS:-30}"
DIGEST_DATE="${DIGEST_DATE:-}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "[ERROR] PROJECT_ID is required"
  echo "Example: PROJECT_ID=daily-digest-app-495805 ./scripts/gcp_release_run.sh"
  exit 1
fi

if [[ -z "${CLOUDSDK_CONFIG:-}" ]]; then
  export CLOUDSDK_CONFIG="$PWD/.gcloud-config"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

run_stage() {
  local stage_name="$1"
  shift

  echo ""
  echo "============================================================"
  echo "[STAGE] $stage_name"
  echo "============================================================"

  if [[ "$DRY_RUN" == "true" ]]; then
    echo "[DRY-RUN] $*"
  else
    "$@"
  fi
}

if [[ "$RUN_PREFLIGHT" == "true" ]]; then
  PREFLIGHT_CMD=(
    env
    PROJECT_ID="$PROJECT_ID"
    REGION="$REGION"
    BILLING_ACCOUNT_ID="$BILLING_ACCOUNT_ID"
    "$SCRIPT_DIR/gcp_preflight.sh"
  )
  run_stage "Preflight" "${PREFLIGHT_CMD[@]}"
else
  echo "[INFO] Skipping preflight"
fi

if [[ "$RUN_SECRETS" == "true" ]]; then
  SECRETS_CMD=(
    env
    PROJECT_ID="$PROJECT_ID"
    "$SCRIPT_DIR/setup_gcp_secrets.sh"
  )
  run_stage "Secret Bootstrap" "${SECRETS_CMD[@]}"
else
  echo "[INFO] Skipping secret bootstrap"
fi

if [[ "$RUN_DEPLOY" == "true" ]]; then
  DEPLOY_CMD=(
    env
    PROJECT_ID="$PROJECT_ID"
    REGION="$REGION"
    TIMEZONE="$TIMEZONE"
    SCHEDULE="$SCHEDULE"
    SMOKE_EXECUTE="$SMOKE_EXECUTE"
    "$SCRIPT_DIR/deploy_gcp_cloud_run_job.sh"
  )
  run_stage "Deploy" "${DEPLOY_CMD[@]}"
else
  echo "[INFO] Skipping deploy"
fi

if [[ "$RUN_HEALTH" == "true" ]]; then
  HEALTH_CMD=(
    env
    PROJECT_ID="$PROJECT_ID"
    REGION="$REGION"
    TIMEZONE="$TIMEZONE"
    MAX_EXECUTION_AGE_HOURS="$MAX_EXECUTION_AGE_HOURS"
    "$SCRIPT_DIR/gcp_health_check.sh"
  )
  run_stage "Health Check" "${HEALTH_CMD[@]}"
else
  echo "[INFO] Skipping health check"
fi

if [[ "$RUN_VALIDATE_DRIVE" == "true" ]]; then
  VALIDATE_CMD=(
    env
    PROJECT_ID="$PROJECT_ID"
    REGION="$REGION"
    DIGEST_DATE="$DIGEST_DATE"
    "$SCRIPT_DIR/gcp_validate_drive_output.sh"
  )
  run_stage "Drive Output Validation" "${VALIDATE_CMD[@]}"
else
  echo "[INFO] Skipping drive output validation"
fi

echo ""
echo "[SUCCESS] Release runner completed"
echo "[INFO] Project=$PROJECT_ID Region=$REGION Timezone=$TIMEZONE Schedule='$SCHEDULE'"
