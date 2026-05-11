#!/usr/bin/env bash
set -euo pipefail

# Verify that the storageQuotaExceeded incident path is resolved in Cloud Run.
#
# Checks performed:
# 1) Executes Cloud Run job once (optional)
# 2) Confirms execution-scoped logs show oauth_user auth and safe upload branch
# 3) Confirms logs do not contain storage quota/fallback-rename signatures
# 4) Validates Drive artifact for current and previous business dates
#
# Usage:
#   PROJECT_ID=daily-digest-app-495805 REGION=asia-southeast1 ./scripts/gcp_verify_storage_issue_fix.sh
#
# Optional env vars:
#   JOB_NAME=daily-digest
#   TIMEZONE=Asia/Jakarta
#   RUN_MANUAL_EXECUTION=true
#   DIGEST_DATE=2026-05-11
#   PREVIOUS_DIGEST_DATE=2026-05-10
#   REQUIRE_PREVIOUS_DATE_PRESENT=false

PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-asia-southeast1}"
JOB_NAME="${JOB_NAME:-daily-digest}"
TIMEZONE="${TIMEZONE:-Asia/Jakarta}"
RUN_MANUAL_EXECUTION="${RUN_MANUAL_EXECUTION:-true}"
DIGEST_DATE="${DIGEST_DATE:-}"
PREVIOUS_DIGEST_DATE="${PREVIOUS_DIGEST_DATE:-}"
REQUIRE_PREVIOUS_DATE_PRESENT="${REQUIRE_PREVIOUS_DATE_PRESENT:-false}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "[ERROR] PROJECT_ID is required"
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

echo "[INFO] Using gcloud: $GCLOUD_BIN"
echo "[INFO] CLOUDSDK_CONFIG: $CLOUDSDK_CONFIG"
"$GCLOUD_BIN" config set project "$PROJECT_ID" >/dev/null

if [[ -z "$DIGEST_DATE" || -z "$PREVIOUS_DIGEST_DATE" ]]; then
  export TIMEZONE
  DATE_PAIR="$(python3 - <<'PY'
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os

tz = ZoneInfo(os.environ["TIMEZONE"])
today = datetime.now(tz).date()
prev = today - timedelta(days=1)
print(today.strftime("%Y-%m-%d"))
print(prev.strftime("%Y-%m-%d"))
PY
)"
  [[ -z "$DIGEST_DATE" ]] && DIGEST_DATE="$(printf '%s' "$DATE_PAIR" | sed -n '1p')"
  [[ -z "$PREVIOUS_DIGEST_DATE" ]] && PREVIOUS_DIGEST_DATE="$(printf '%s' "$DATE_PAIR" | sed -n '2p')"
fi

EXECUTION_NAME=""
if [[ "$RUN_MANUAL_EXECUTION" == "true" ]]; then
  echo "[STEP] Executing Cloud Run job once for verification"
  "$GCLOUD_BIN" run jobs execute "$JOB_NAME" --region "$REGION" --wait >/dev/null
fi

EXECUTION_NAME="$($GCLOUD_BIN run jobs executions list \
  --region "$REGION" \
  --job "$JOB_NAME" \
  --limit 1 \
  --sort-by='~createTime' \
  --format='value(name)' 2>/dev/null || true)"

if [[ -z "$EXECUTION_NAME" ]]; then
  echo "[ERROR] Unable to resolve latest execution name"
  exit 1
fi

echo "[INFO] Verification execution: $EXECUTION_NAME"

LOG_LINES="$($GCLOUD_BIN logging read \
  "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"$JOB_NAME\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXECUTION_NAME\"" \
  --project "$PROJECT_ID" \
  --limit 400 \
  --format='value(textPayload)' 2>/dev/null || true)"

if [[ -z "$LOG_LINES" ]]; then
  echo "[ERROR] No execution-scoped log lines found for $EXECUTION_NAME"
  exit 1
fi

echo "[STEP] Checking auth and branch markers in logs"
if ! printf '%s\n' "$LOG_LINES" | grep -q "Using oauth_user auth for Drive upload"; then
  echo "[ERROR] oauth_user auth marker not found in execution logs"
  exit 1
fi

if ! printf '%s\n' "$LOG_LINES" | grep -Eq "Drive upload branch=(same_name_update|create_new)"; then
  echo "[ERROR] Safe upload branch marker not found (same_name_update/create_new)"
  exit 1
fi

if printf '%s\n' "$LOG_LINES" | grep -Eq "storageQuotaExceeded|Drive create failed due to storage quota|create_quota_failure|attempting fallback update of latest digest file"; then
  echo "[ERROR] Detected legacy quota/fallback markers in execution logs"
  exit 1
fi

echo "[OK] Execution logs indicate quota issue path is not triggered"

echo "[STEP] Validating Drive artifact for current business date: $DIGEST_DATE"
PROJECT_ID="$PROJECT_ID" REGION="$REGION" TIMEZONE="$TIMEZONE" DIGEST_DATE="$DIGEST_DATE" \
  ./scripts/gcp_validate_drive_output.sh

echo "[STEP] Validating Drive artifact for previous business date: $PREVIOUS_DIGEST_DATE"
set +e
PROJECT_ID="$PROJECT_ID" REGION="$REGION" TIMEZONE="$TIMEZONE" DIGEST_DATE="$PREVIOUS_DIGEST_DATE" \
  ./scripts/gcp_validate_drive_output.sh
PREV_EXIT=$?
set -e

if [[ "$PREV_EXIT" -ne 0 ]]; then
  if [[ "$REQUIRE_PREVIOUS_DATE_PRESENT" == "true" ]]; then
    echo "[ERROR] Previous-date artifact validation failed and strict continuity is required"
    exit 1
  fi
  echo "[WARN] Previous-date artifact not found. This may be a legacy data gap; continuing because REQUIRE_PREVIOUS_DATE_PRESENT=false"
else
  echo "[OK] Previous-date artifact exists"
fi

echo "[SUCCESS] Storage-issue verification passed"
echo "[INFO] Execution: $EXECUTION_NAME"
echo "[INFO] Current date artifact: $DIGEST_DATE"
echo "[INFO] Previous date artifact: $PREVIOUS_DIGEST_DATE"
