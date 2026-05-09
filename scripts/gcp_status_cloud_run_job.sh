#!/usr/bin/env bash
set -euo pipefail

# Read-only status helper for Cloud Run Job deployment.
# Usage example:
# PROJECT_ID=daily-digest-app-495805 REGION=asia-southeast1 ./scripts/gcp_status_cloud_run_job.sh

PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-asia-southeast1}"
JOB_NAME="${JOB_NAME:-daily-digest}"
SCHEDULER_NAME="${SCHEDULER_NAME:-daily-digest}"

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

ACCOUNT="$($GCLOUD_BIN auth list --filter=status:ACTIVE --format='value(account)' || true)"
ACTIVE_PROJECT="$($GCLOUD_BIN config get-value project 2>/dev/null || true)"

echo "[INFO] Active account: ${ACCOUNT:-<none>}"
echo "[INFO] Active project: ${ACTIVE_PROJECT:-<none>}"

if [[ "$ACTIVE_PROJECT" != "$PROJECT_ID" ]]; then
  echo "[INFO] Setting project context to $PROJECT_ID"
  "$GCLOUD_BIN" config set project "$PROJECT_ID" >/dev/null
fi

echo ""
echo "== Cloud Run Job =="
if "$GCLOUD_BIN" run jobs describe "$JOB_NAME" --region "$REGION" >/dev/null 2>&1; then
  "$GCLOUD_BIN" run jobs describe "$JOB_NAME" --region "$REGION" \
    --format='table(metadata.name,spec.template.template.spec.containers[0].image,status.conditions[0].type,status.conditions[0].state,status.conditions[0].lastTransitionTime)'
else
  echo "[WARN] Job not found: $JOB_NAME ($REGION)"
fi

echo ""
echo "== Recent Executions =="
if "$GCLOUD_BIN" run jobs executions list --region "$REGION" --job "$JOB_NAME" --limit 3 >/dev/null 2>&1; then
  "$GCLOUD_BIN" run jobs executions list --region "$REGION" --job "$JOB_NAME" --limit 3 \
    --format='table(name,completionStatus,createTime,completionTime)'
else
  echo "[WARN] Unable to fetch execution list (may be unsupported in this gcloud version or no executions yet)."
fi

echo ""
echo "== Cloud Scheduler =="
if "$GCLOUD_BIN" scheduler jobs describe "$SCHEDULER_NAME" --location "$REGION" >/dev/null 2>&1; then
  "$GCLOUD_BIN" scheduler jobs describe "$SCHEDULER_NAME" --location "$REGION" \
    --format='table(name,schedule,timeZone,state,lastAttemptTime)'
else
  echo "[WARN] Scheduler job not found: $SCHEDULER_NAME ($REGION)"
fi

echo ""
echo "[SUCCESS] Status check complete (read-only)"
