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
#   RUN_VERIFY_STORAGE_FIX=true # default true
#   RUN_VERIFY_PARITY=true      # default true
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
RUN_VERIFY_STORAGE_FIX="${RUN_VERIFY_STORAGE_FIX:-true}"
RUN_VERIFY_PARITY="${RUN_VERIFY_PARITY:-true}"

DRY_RUN="${DRY_RUN:-false}"
SMOKE_EXECUTE="${SMOKE_EXECUTE:-false}"
MAX_EXECUTION_AGE_HOURS="${MAX_EXECUTION_AGE_HOURS:-30}"
DIGEST_DATE="${DIGEST_DATE:-}"
JOB_NAME="${JOB_NAME:-daily-digest}"
USE_OAUTH_USER_DRIVE="${USE_OAUTH_USER_DRIVE:-true}"
APP_VERSION="${APP_VERSION:-}"
IMAGE_TAG="${IMAGE_TAG:-}"
VERIFY_STORAGE_RUN_MANUAL_EXECUTION="${VERIFY_STORAGE_RUN_MANUAL_EXECUTION:-false}"
VERIFY_STORAGE_REQUIRE_PREVIOUS_DATE_PRESENT="${VERIFY_STORAGE_REQUIRE_PREVIOUS_DATE_PRESENT:-false}"
PARITY_BRANCH="${PARITY_BRANCH:-main}"
PARITY_REQUIRE_CLEAN_WORKTREE="${PARITY_REQUIRE_CLEAN_WORKTREE:-true}"
PARITY_REQUIRE_LOCAL_DOCKER_IMAGE="${PARITY_REQUIRE_LOCAL_DOCKER_IMAGE:-true}"
EXPECTED_APP_VERSION="${EXPECTED_APP_VERSION:-}"

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
    USE_OAUTH_USER_DRIVE="$USE_OAUTH_USER_DRIVE"
    APP_VERSION="$APP_VERSION"
    IMAGE_TAG="$IMAGE_TAG"
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
    JOB_NAME="$JOB_NAME"
    DIGEST_DATE="$DIGEST_DATE"
    "$SCRIPT_DIR/gcp_validate_drive_output.sh"
  )
  run_stage "Drive Output Validation" "${VALIDATE_CMD[@]}"
else
  echo "[INFO] Skipping drive output validation"
fi

if [[ "$RUN_VERIFY_STORAGE_FIX" == "true" ]]; then
  VERIFY_STORAGE_CMD=(
    env
    PROJECT_ID="$PROJECT_ID"
    REGION="$REGION"
    JOB_NAME="$JOB_NAME"
    TIMEZONE="$TIMEZONE"
    RUN_MANUAL_EXECUTION="$VERIFY_STORAGE_RUN_MANUAL_EXECUTION"
    REQUIRE_PREVIOUS_DATE_PRESENT="$VERIFY_STORAGE_REQUIRE_PREVIOUS_DATE_PRESENT"
    DIGEST_DATE="$DIGEST_DATE"
    "$SCRIPT_DIR/gcp_verify_storage_issue_fix.sh"
  )
  run_stage "Storage Fix Verification" "${VERIFY_STORAGE_CMD[@]}"
else
  echo "[INFO] Skipping storage-fix verification"
fi

if [[ "$RUN_VERIFY_PARITY" == "true" ]]; then
  PARITY_CMD=(
    env
    PROJECT_ID="$PROJECT_ID"
    REGION="$REGION"
    JOB_NAME="$JOB_NAME"
    BRANCH="$PARITY_BRANCH"
    REQUIRE_CLEAN_WORKTREE="$PARITY_REQUIRE_CLEAN_WORKTREE"
    REQUIRE_LOCAL_DOCKER_IMAGE="$PARITY_REQUIRE_LOCAL_DOCKER_IMAGE"
    EXPECTED_APP_VERSION="$EXPECTED_APP_VERSION"
    "$SCRIPT_DIR/gcp_verify_release_parity.sh"
  )
  run_stage "Release Parity Verification" "${PARITY_CMD[@]}"
else
  echo "[INFO] Skipping release parity verification"
fi

echo ""
echo "[SUCCESS] Release runner completed"
echo "[INFO] Project=$PROJECT_ID Region=$REGION Timezone=$TIMEZONE Schedule='$SCHEDULE'"
