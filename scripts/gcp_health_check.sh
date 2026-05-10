#!/usr/bin/env bash
set -euo pipefail

# One-command health check for scheduled Cloud Run Job operation.
#
# Usage:
#   PROJECT_ID=daily-digest-app-495805 REGION=asia-southeast1 ./scripts/gcp_health_check.sh
#
# Optional env vars:
#   JOB_NAME=daily-digest
#   SCHEDULER_NAME=daily-digest
#   TIMEZONE=Asia/Hong_Kong
#   MAX_EXECUTION_AGE_HOURS=30
#   REQUIRE_EXPECTED_RUN=true
#   REQUIRE_SUCCESS=true

PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-asia-southeast1}"
JOB_NAME="${JOB_NAME:-daily-digest}"
SCHEDULER_NAME="${SCHEDULER_NAME:-daily-digest}"
TIMEZONE="${TIMEZONE:-Asia/Hong_Kong}"
MAX_EXECUTION_AGE_HOURS="${MAX_EXECUTION_AGE_HOURS:-30}"
REQUIRE_EXPECTED_RUN="${REQUIRE_EXPECTED_RUN:-true}"
REQUIRE_SUCCESS="${REQUIRE_SUCCESS:-true}"

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
if [[ -z "$ACCOUNT" ]]; then
  echo "[ERROR] No active gcloud account"
  exit 1
fi

echo "[OK] Active account: $ACCOUNT"
"$GCLOUD_BIN" config set project "$PROJECT_ID" >/dev/null

echo "[STEP] Checking Cloud Run job"
if ! "$GCLOUD_BIN" run jobs describe "$JOB_NAME" --region "$REGION" >/dev/null 2>&1; then
  echo "[ERROR] Cloud Run job not found: $JOB_NAME ($REGION)"
  exit 1
fi

JOB_JSON="$($GCLOUD_BIN run jobs describe "$JOB_NAME" --region "$REGION" --format=json)"
JOB_READY_STATUS="$(printf '%s' "$JOB_JSON" | python3 -c 'import json,sys; data=json.load(sys.stdin); conds=data.get("status",{}).get("conditions",[]); ready=""; 
for c in conds:
  if c.get("type")=="Ready":
    ready=c.get("status","")
    break
print(ready)')"
if [[ "$JOB_READY_STATUS" == "True" ]]; then
  echo "[OK] Cloud Run job appears ready"
else
  echo "[WARN] Unexpected job ready status: ${JOB_READY_STATUS:-<empty>}"
fi

echo "[STEP] Checking Cloud Scheduler"
if ! "$GCLOUD_BIN" scheduler jobs describe "$SCHEDULER_NAME" --location "$REGION" >/dev/null 2>&1; then
  echo "[ERROR] Scheduler job not found: $SCHEDULER_NAME ($REGION)"
  exit 1
fi

SCHEDULER_STATE="$($GCLOUD_BIN scheduler jobs describe "$SCHEDULER_NAME" --location "$REGION" --format='value(state)' 2>/dev/null || true)"
SCHEDULER_CRON="$($GCLOUD_BIN scheduler jobs describe "$SCHEDULER_NAME" --location "$REGION" --format='value(schedule)' 2>/dev/null || true)"
SCHEDULER_TZ="$($GCLOUD_BIN scheduler jobs describe "$SCHEDULER_NAME" --location "$REGION" --format='value(timeZone)' 2>/dev/null || true)"
SCHEDULER_LAST_ATTEMPT="$($GCLOUD_BIN scheduler jobs describe "$SCHEDULER_NAME" --location "$REGION" --format='value(lastAttemptTime)' 2>/dev/null || true)"

if [[ "$SCHEDULER_STATE" != "ENABLED" ]]; then
  echo "[ERROR] Scheduler is not enabled: ${SCHEDULER_STATE:-<empty>}"
  exit 1
fi

echo "[OK] Scheduler enabled: $SCHEDULER_NAME"
echo "[INFO] Scheduler config: cron='${SCHEDULER_CRON:-<unknown>}' timezone='${SCHEDULER_TZ:-<unknown>}'"
echo "[INFO] Scheduler lastAttemptTime: ${SCHEDULER_LAST_ATTEMPT:-<empty>}"

if [[ -n "$SCHEDULER_TZ" && "$SCHEDULER_TZ" != "$TIMEZONE" ]]; then
  echo "[WARN] Scheduler timezone differs from expected: expected=$TIMEZONE actual=$SCHEDULER_TZ"
fi

echo "[STEP] Checking latest execution"
LATEST_EXECUTION="$($GCLOUD_BIN run jobs executions list --region "$REGION" --job "$JOB_NAME" --limit 1 --sort-by='~createTime' --format='value(name)' 2>/dev/null || true)"

if [[ -z "$LATEST_EXECUTION" ]]; then
  echo "[ERROR] No executions found for job: $JOB_NAME"
  exit 1
fi

EXEC_JSON="$($GCLOUD_BIN run jobs executions describe "$LATEST_EXECUTION" --region "$REGION" --format=json)"
EXEC_FIELDS="$(printf '%s' "$EXEC_JSON" | python3 -c 'import json,sys; data=json.load(sys.stdin); conds=data.get("status",{}).get("conditions",[]); cs=""; cm=""; 
for c in conds:
  if c.get("type")=="Completed":
    cs=c.get("status","")
    cm=c.get("message","")
    break
creation=data.get("metadata",{}).get("creationTimestamp","")
completion=data.get("status",{}).get("completionTime","")
log_uri=data.get("status",{}).get("logUri","")
print(cs); print(creation); print(completion); print(cm); print(log_uri)')"

LATEST_STATUS="$(printf '%s' "$EXEC_FIELDS" | sed -n '1p')"
LATEST_CREATE_TIME="$(printf '%s' "$EXEC_FIELDS" | sed -n '2p')"
LATEST_COMPLETE_TIME="$(printf '%s' "$EXEC_FIELDS" | sed -n '3p')"
LATEST_MESSAGE="$(printf '%s' "$EXEC_FIELDS" | sed -n '4p')"
LATEST_LOG_URI="$(printf '%s' "$EXEC_FIELDS" | sed -n '5p')"

echo "[INFO] Latest execution: $LATEST_EXECUTION"
echo "[INFO] Latest status: ${LATEST_STATUS:-<empty>}"
echo "[INFO] Latest createTime: ${LATEST_CREATE_TIME:-<empty>}"
echo "[INFO] Latest completionTime: ${LATEST_COMPLETE_TIME:-<empty>}"
echo "[INFO] Latest message: ${LATEST_MESSAGE:-<empty>}"
echo "[INFO] Latest logUri: ${LATEST_LOG_URI:-<empty>}"

if [[ "$REQUIRE_SUCCESS" == "true" ]]; then
  if [[ "$LATEST_STATUS" != "True" ]]; then
    echo "[ERROR] Latest execution is not successful"
    exit 1
  fi
  echo "[OK] Latest execution succeeded"
fi

if [[ -n "$LATEST_CREATE_TIME" ]]; then
  export LATEST_CREATE_TIME MAX_EXECUTION_AGE_HOURS
  AGE_RESULT="$(python3 - <<'PY'
import datetime
import os
import sys

created = os.environ.get("LATEST_CREATE_TIME", "").strip()
max_age = float(os.environ.get("MAX_EXECUTION_AGE_HOURS", "30"))

if not created:
    print("unknown")
    sys.exit(0)

try:
    dt = datetime.datetime.fromisoformat(created.replace("Z", "+00:00"))
except Exception:
    print("parse-error")
    sys.exit(0)

now = datetime.datetime.now(datetime.timezone.utc)
age_hours = (now - dt.astimezone(datetime.timezone.utc)).total_seconds() / 3600.0
print(f"{age_hours:.2f}")
print("ok" if age_hours <= max_age else "stale")
PY
)"

  AGE_HOURS="$(printf '%s' "$AGE_RESULT" | sed -n '1p')"
  AGE_STATE="$(printf '%s' "$AGE_RESULT" | sed -n '2p')"

  if [[ "$AGE_STATE" == "parse-error" ]]; then
    echo "[WARN] Could not parse createTime for age check"
  elif [[ "$AGE_STATE" == "unknown" ]]; then
    echo "[WARN] createTime unavailable for age check"
  elif [[ "$AGE_STATE" == "stale" ]]; then
    echo "[ERROR] Latest execution is stale: ${AGE_HOURS}h old (max ${MAX_EXECUTION_AGE_HOURS}h)"
    exit 1
  else
    echo "[OK] Latest execution freshness: ${AGE_HOURS}h old"
  fi
fi

if [[ "$REQUIRE_EXPECTED_RUN" == "true" ]]; then
  export LATEST_CREATE_TIME SCHEDULER_LAST_ATTEMPT SCHEDULER_CRON TIMEZONE
  EXPECTED_RUN_RESULT="$(python3 - <<'PY'
import datetime
import os
import sys
from zoneinfo import ZoneInfo


def parse_iso8601(value: str) -> datetime.datetime | None:
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


cron = os.environ.get("SCHEDULER_CRON", "").strip()
tz_name = os.environ.get("TIMEZONE", "").strip()
latest_create = parse_iso8601(os.environ.get("LATEST_CREATE_TIME", "").strip())
scheduler_last_attempt = parse_iso8601(os.environ.get("SCHEDULER_LAST_ATTEMPT", "").strip())

parts = cron.split()
if len(parts) != 5:
    print("unsupported")
    sys.exit(0)

minute, hour, day_of_month, month, day_of_week = parts
if not (minute.isdigit() and hour.isdigit() and day_of_month == "*" and month == "*" and day_of_week == "*"):
    print("unsupported")
    sys.exit(0)

try:
    tz = ZoneInfo(tz_name)
except Exception:
    print("invalid-timezone")
    sys.exit(0)

now_local = datetime.datetime.now(tz)
expected_local = now_local.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
if now_local < expected_local:
    expected_local -= datetime.timedelta(days=1)

expected_utc = expected_local.astimezone(datetime.timezone.utc)
print(expected_local.isoformat())
print(expected_utc.isoformat())

if scheduler_last_attempt is None:
    print("missing-last-attempt")
else:
    print("scheduler-ok" if scheduler_last_attempt.astimezone(datetime.timezone.utc) >= expected_utc else "scheduler-stale")

if latest_create is None:
    print("missing-execution")
else:
    print("execution-ok" if latest_create.astimezone(datetime.timezone.utc) >= expected_utc else "execution-stale")
PY
)"

  EXPECTED_LOCAL_TIME="$(printf '%s' "$EXPECTED_RUN_RESULT" | sed -n '1p')"
  EXPECTED_UTC_TIME="$(printf '%s' "$EXPECTED_RUN_RESULT" | sed -n '2p')"
  EXPECTED_SCHEDULER_STATE="$(printf '%s' "$EXPECTED_RUN_RESULT" | sed -n '3p')"
  EXPECTED_EXECUTION_STATE="$(printf '%s' "$EXPECTED_RUN_RESULT" | sed -n '4p')"

  if [[ "$EXPECTED_LOCAL_TIME" == "unsupported" ]]; then
    echo "[WARN] Expected-run validation skipped: unsupported cron expression '${SCHEDULER_CRON:-<empty>}'"
  elif [[ "$EXPECTED_LOCAL_TIME" == "invalid-timezone" ]]; then
    echo "[WARN] Expected-run validation skipped: invalid timezone '$TIMEZONE'"
  else
    echo "[INFO] Expected latest scheduled run: local=${EXPECTED_LOCAL_TIME:-<empty>} utc=${EXPECTED_UTC_TIME:-<empty>}"

    if [[ "$EXPECTED_SCHEDULER_STATE" == "missing-last-attempt" ]]; then
      echo "[ERROR] Scheduler has no lastAttemptTime; cannot confirm the expected run was triggered"
      exit 1
    elif [[ "$EXPECTED_SCHEDULER_STATE" == "scheduler-stale" ]]; then
      echo "[ERROR] Scheduler lastAttemptTime predates the expected scheduled run"
      exit 1
    else
      echo "[OK] Scheduler attempted the latest expected run window"
    fi

    if [[ "$EXPECTED_EXECUTION_STATE" == "missing-execution" ]]; then
      echo "[ERROR] Latest execution createTime unavailable; cannot confirm the expected run executed"
      exit 1
    elif [[ "$EXPECTED_EXECUTION_STATE" == "execution-stale" ]]; then
      echo "[ERROR] Latest execution predates the latest expected scheduled run"
      exit 1
    else
      echo "[OK] Latest execution matches the latest expected run window"
    fi
  fi
fi

echo "[SUCCESS] Health check passed"
