#!/usr/bin/env bash
set -euo pipefail

# Validate that today's digest file exists in Google Drive.
#
# This script reads service-account JSON from Secret Manager and queries
# Google Drive for a file named:
#   Daily AI and Technology Digest - YYYY-MM-DD.*
# in the configured Drive folder.
#
# Usage:
#   PROJECT_ID=daily-digest-app-495805 REGION=asia-southeast1 ./scripts/gcp_validate_drive_output.sh
#
# Optional env vars:
#   DIGEST_DATE=2026-05-09
#   TIMEZONE=Asia/Hong_Kong
#   EXECUTION_NAME=daily-digest-abc12
#   STRICT_PDF_ONLY=true
#   GOOGLE_DRIVE_FOLDER_ID=...
#   GOOGLE_SERVICE_ACCOUNT_SECRET=google-service-account-json
#   JOB_NAME=daily-digest

PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-asia-southeast1}"
TIMEZONE="${TIMEZONE:-Asia/Hong_Kong}"
DIGEST_DATE="${DIGEST_DATE:-}"
EXECUTION_NAME="${EXECUTION_NAME:-}"
STRICT_PDF_ONLY="${STRICT_PDF_ONLY:-true}"
GOOGLE_DRIVE_FOLDER_ID="${GOOGLE_DRIVE_FOLDER_ID:-}"
GOOGLE_SERVICE_ACCOUNT_SECRET="${GOOGLE_SERVICE_ACCOUNT_SECRET:-google-service-account-json}"
JOB_NAME="${JOB_NAME:-daily-digest}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "[ERROR] PROJECT_ID is required"
  exit 1
fi

if [[ -z "$DIGEST_DATE" ]]; then
  export TIMEZONE
  DIGEST_DATE="$(python3 - <<'PY'
from datetime import datetime
import os
from zoneinfo import ZoneInfo

print(datetime.now(ZoneInfo(os.environ["TIMEZONE"])).strftime("%Y-%m-%d"))
PY
)"
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

if [[ -z "$GOOGLE_DRIVE_FOLDER_ID" && -f .env ]]; then
  GOOGLE_DRIVE_FOLDER_ID="$(grep -E '^[[:space:]]*GOOGLE_DRIVE_FOLDER_ID=' .env | tail -n 1 | sed 's/^[^=]*=//')"
fi

if [[ -z "$GOOGLE_DRIVE_FOLDER_ID" ]]; then
  echo "[ERROR] GOOGLE_DRIVE_FOLDER_ID is required (env var or .env)"
  exit 1
fi

echo "[INFO] Using gcloud: $GCLOUD_BIN"
"$GCLOUD_BIN" config set project "$PROJECT_ID" >/dev/null

if ! "$GCLOUD_BIN" secrets describe "$GOOGLE_SERVICE_ACCOUNT_SECRET" >/dev/null 2>&1; then
  echo "[ERROR] Secret not found: $GOOGLE_SERVICE_ACCOUNT_SECRET"
  exit 1
fi

SA_JSON="$($GCLOUD_BIN secrets versions access latest --secret="$GOOGLE_SERVICE_ACCOUNT_SECRET")"
if [[ -z "$SA_JSON" ]]; then
  echo "[ERROR] Service-account secret is empty: $GOOGLE_SERVICE_ACCOUNT_SECRET"
  exit 1
fi

export SA_JSON GOOGLE_DRIVE_FOLDER_ID DIGEST_DATE

set +e
VALIDATION_OUTPUT="$(python3 - <<'PY'
import json
import os
import sys

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
except Exception as e:
    print(f"error:missing_python_dependency:{e}")
    sys.exit(2)

sa_json = os.environ["SA_JSON"]
folder_id = os.environ["GOOGLE_DRIVE_FOLDER_ID"]
digest_date = os.environ["DIGEST_DATE"]

try:
    info = json.loads(sa_json)
except Exception as e:
    print(f"error:invalid_sa_json:{e}")
    sys.exit(2)

creds = Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/drive.readonly"])
service = build("drive", "v3", credentials=creds, cache_discovery=False)

prefix = f"Daily AI and Technology Digest - {digest_date}"
query = (
    f"trashed=false and '{folder_id}' in parents and "
  f"name contains '{prefix}'"
)

res = service.files().list(
    q=query,
    fields="files(id,name,modifiedTime,size,webViewLink)",
    orderBy="modifiedTime desc",
    pageSize=5,
).execute()

files = res.get("files", [])
if not files:
    print("missing")
    sys.exit(1)

f = files[0]
print("found")
print(f.get("id", ""))
print(f.get("name", ""))
print(f.get("modifiedTime", ""))
print(f.get("size", ""))
print(f.get("webViewLink", ""))
PY
)"
PY_EXIT=$?
set -e

STATUS="$(printf '%s' "$VALIDATION_OUTPUT" | sed -n '1p')"
if [[ "$STATUS" == "found" ]]; then
  FILE_ID="$(printf '%s' "$VALIDATION_OUTPUT" | sed -n '2p')"
  FILE_NAME="$(printf '%s' "$VALIDATION_OUTPUT" | sed -n '3p')"
  FILE_MODIFIED="$(printf '%s' "$VALIDATION_OUTPUT" | sed -n '4p')"
  FILE_SIZE="$(printf '%s' "$VALIDATION_OUTPUT" | sed -n '5p')"
  FILE_URL="$(printf '%s' "$VALIDATION_OUTPUT" | sed -n '6p')"

  if [[ "$STRICT_PDF_ONLY" == "true" ]]; then
    if [[ ! "$FILE_NAME" =~ \.pdf$ ]]; then
      echo "[ERROR] Strict PDF mode: expected .pdf artifact but found '$FILE_NAME'"
      exit 1
    fi
  fi

  echo "[OK] Drive digest file found for date $DIGEST_DATE"
  echo "[INFO] name: ${FILE_NAME:-<empty>}"
  echo "[INFO] id: ${FILE_ID:-<empty>}"
  echo "[INFO] modified: ${FILE_MODIFIED:-<empty>}"
  echo "[INFO] size: ${FILE_SIZE:-<empty>}"
  echo "[INFO] url: ${FILE_URL:-<empty>}"
  echo "[SUCCESS] Drive output validation passed"
  exit 0
fi

if [[ "$STATUS" == error:* ]]; then
  ERROR_KIND="${STATUS#error:}"
  if [[ "$ERROR_KIND" == missing_python_dependency:* ]]; then
    echo "[WARN] ${ERROR_KIND}"
    echo "[INFO] Falling back to Cloud Run log-based validation"

    if [[ -z "$EXECUTION_NAME" ]]; then
      EXECUTION_NAME="$(
        "$GCLOUD_BIN" run jobs executions list \
          --region "$REGION" \
          --job "$JOB_NAME" \
          --limit 1 \
          --sort-by='~createTime' \
          --format='value(name)' 2>/dev/null || true
      )"
    fi

    LATEST_UPLOAD_LINE=""
    if [[ -n "$EXECUTION_NAME" ]]; then
      echo "[INFO] Validating logs for execution: $EXECUTION_NAME"
      LATEST_UPLOAD_LINE="$(
        "$GCLOUD_BIN" logging read \
          "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"$JOB_NAME\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXECUTION_NAME\"" \
          --project "$PROJECT_ID" \
          --limit 200 \
          --format='value(timestamp,textPayload)' 2>/dev/null | \
        grep -E "Successfully uploaded to Drive( for business date)?" | \
        grep -E "\.pdf|file/d/" | \
        grep "$DIGEST_DATE" | \
        tail -n 1 || true
      )"
    fi

    if [[ -z "$LATEST_UPLOAD_LINE" ]]; then
      if [[ -n "$EXECUTION_NAME" ]]; then
        echo "[ERROR] No successful Drive upload log found for execution $EXECUTION_NAME"
        exit 1
      fi
      echo "[WARN] Execution-scoped upload log not found; trying broad job log search"
      LATEST_UPLOAD_LINE="$(
        "$GCLOUD_BIN" run jobs logs read "$JOB_NAME" \
          --region "$REGION" \
          --project "$PROJECT_ID" \
          --limit=300 2>/dev/null | \
        grep -E "Successfully uploaded to Drive( for business date)?" | \
        grep -E "\.pdf|file/d/" | \
        grep "$DIGEST_DATE" | \
        tail -n 1 || true
      )"
    fi

    if [[ -n "$LATEST_UPLOAD_LINE" ]]; then
      echo "[OK] Found same-day successful Drive upload log"
      echo "[INFO] $LATEST_UPLOAD_LINE"
      echo "[SUCCESS] Drive output validation passed (log fallback)"
      exit 0
    fi

    echo "[ERROR] Could not validate Drive upload via fallback logs for $DIGEST_DATE"
    exit 1
  fi

  echo "[ERROR] ${ERROR_KIND}"
  exit 1
fi

if [[ "$PY_EXIT" -ne 0 ]]; then
  echo "[ERROR] Drive validation command failed"
  if [[ -n "$VALIDATION_OUTPUT" ]]; then
    echo "$VALIDATION_OUTPUT"
  fi
  exit 1
fi

echo "[ERROR] No Drive digest file found for date $DIGEST_DATE in folder $GOOGLE_DRIVE_FOLDER_ID"
echo "[INFO] Hint: run a smoke execution and retry:"
echo "       CLOUDSDK_CONFIG=\"$CLOUDSDK_CONFIG\" $GCLOUD_BIN run jobs execute $JOB_NAME --region $REGION --project $PROJECT_ID --wait"
exit 1
