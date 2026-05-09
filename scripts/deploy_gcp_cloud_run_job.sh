#!/usr/bin/env bash
set -euo pipefail

# Usage example:
# PROJECT_ID=daily-digest-app-495805 REGION=asia-southeast1 SCHEDULE="0 7 * * *" TIMEZONE="Asia/Hong_Kong" ./scripts/deploy_gcp_cloud_run_job.sh

PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-asia-southeast1}"
REPOSITORY="${REPOSITORY:-digest}"
JOB_NAME="${JOB_NAME:-daily-digest}"
IMAGE_NAME="${IMAGE_NAME:-daily-digest}"
IMAGE_TAG="${IMAGE_TAG:-1.0}"
SCHEDULER_NAME="${SCHEDULER_NAME:-daily-digest}"
SCHEDULE="${SCHEDULE:-0 7 * * *}"
TIMEZONE="${TIMEZONE:-UTC}"
SMOKE_EXECUTE="${SMOKE_EXECUTE:-false}"

RUNTIME_SA_NAME="${RUNTIME_SA_NAME:-digest-runner}"
SCHEDULER_SA_NAME="${SCHEDULER_SA_NAME:-cloud-scheduler-digest}"

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

# Homebrew Cloud SDK installs docker-credential-gcloud here; include it in PATH
# so `gcloud auth configure-docker` works in non-interactive script runs.
if [[ -d "/opt/homebrew/share/google-cloud-sdk/bin" ]]; then
  export PATH="/opt/homebrew/share/google-cloud-sdk/bin:$PATH"
fi

AR_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:${IMAGE_TAG}"
RUNTIME_SA="${RUNTIME_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
SCHEDULER_SA="${SCHEDULER_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
JOB_RUN_URI="https://run.googleapis.com/v2/projects/${PROJECT_ID}/locations/${REGION}/jobs/${JOB_NAME}:run"

retry_gcloud() {
  local attempts="${RETRY_ATTEMPTS:-5}"
  local delay="${RETRY_INITIAL_DELAY_SECONDS:-2}"
  local i

  for ((i=1; i<=attempts; i++)); do
    if "$GCLOUD_BIN" "$@"; then
      return 0
    fi

    if [[ "$i" -eq "$attempts" ]]; then
      echo "[ERROR] gcloud command failed after $attempts attempts: gcloud $*"
      return 1
    fi

    echo "[WARN] gcloud command failed (attempt $i/$attempts), retrying in ${delay}s..."
    sleep "$delay"
    delay=$((delay * 2))
  done
}

echo "[INFO] Using gcloud: $GCLOUD_BIN"
"$GCLOUD_BIN" config set project "$PROJECT_ID" >/dev/null

# Enable APIs
retry_gcloud services enable \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com >/dev/null

# Ensure Artifact Registry repo exists
if ! "$GCLOUD_BIN" artifacts repositories describe "$REPOSITORY" --location "$REGION" >/dev/null 2>&1; then
  retry_gcloud artifacts repositories create "$REPOSITORY" \
    --repository-format=docker \
    --location="$REGION" \
    --description="Daily digest images"
fi

# Docker auth + image push
"$GCLOUD_BIN" auth configure-docker "${REGION}-docker.pkg.dev" --quiet

echo "[INFO] Building image: $AR_IMAGE"
if docker buildx version >/dev/null 2>&1; then
  # Cloud Run requires linux/amd64-compatible images.
  docker buildx build --platform linux/amd64 -t "$AR_IMAGE" --push .
else
  # Fallback path if buildx is unavailable.
  docker build -t "$AR_IMAGE" .
  docker push "$AR_IMAGE"
fi

# Service accounts (idempotent)
if ! "$GCLOUD_BIN" iam service-accounts describe "$RUNTIME_SA" >/dev/null 2>&1; then
  retry_gcloud iam service-accounts create "$RUNTIME_SA_NAME" --display-name "Digest Job Runner"
fi
if ! "$GCLOUD_BIN" iam service-accounts describe "$SCHEDULER_SA" >/dev/null 2>&1; then
  retry_gcloud iam service-accounts create "$SCHEDULER_SA_NAME" --display-name "Cloud Scheduler for Digest"
fi

# Runtime SA needs Secret Manager read
retry_gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member "serviceAccount:${RUNTIME_SA}" \
  --role roles/secretmanager.secretAccessor \
  --quiet >/dev/null

# Deploy or update Cloud Run Job
retry_gcloud run jobs deploy "$JOB_NAME" \
  --image "$AR_IMAGE" \
  --region "$REGION" \
  --service-account "$RUNTIME_SA" \
  --memory 512Mi \
  --cpu 1 \
  --max-retries 1 \
  --task-timeout 900s \
  --set-env-vars "RUN_MODE=once,DIGEST_TZ=${TIMEZONE}" \
  --set-secrets "DEEPSEEK_API_KEY=deepseek-key:latest,NEWSAPI_KEY=newsapi-key:latest,GITHUB_TOKEN=github-token:latest,GOOGLE_SERVICE_ACCOUNT_JSON=google-service-account-json:latest"

# Allow scheduler SA to invoke job
retry_gcloud run jobs add-iam-policy-binding "$JOB_NAME" \
  --region "$REGION" \
  --member "serviceAccount:${SCHEDULER_SA}" \
  --role roles/run.invoker >/dev/null

# Create or update Scheduler job
retry_gcloud scheduler jobs create http "$SCHEDULER_NAME" \
  --location "$REGION" \
  --schedule "$SCHEDULE" \
  --time-zone "$TIMEZONE" \
  --uri "$JOB_RUN_URI" \
  --http-method POST \
  --oauth-service-account-email "$SCHEDULER_SA" \
  --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform" \
  --message-body '{}' \
  --max-retry-attempts 1 \
  --min-backoff 300s \
  --max-backoff 3600s \
  >/dev/null 2>&1 || \
retry_gcloud scheduler jobs update http "$SCHEDULER_NAME" \
  --location "$REGION" \
  --schedule "$SCHEDULE" \
  --time-zone "$TIMEZONE" \
  --uri "$JOB_RUN_URI" \
  --http-method POST \
  --oauth-service-account-email "$SCHEDULER_SA" \
  --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform" \
  --message-body '{}' \
  >/dev/null

if [[ "$SMOKE_EXECUTE" == "true" ]]; then
  echo "[INFO] Running smoke execution"
  retry_gcloud run jobs execute "$JOB_NAME" --region "$REGION" --wait
else
  echo "[INFO] Skipping smoke execution (set SMOKE_EXECUTE=true to enable)"
fi

echo "[SUCCESS] Deployment complete"
echo "[INFO] Image: $AR_IMAGE"
echo "[INFO] Job: $JOB_NAME"
echo "[INFO] Scheduler: $SCHEDULER_NAME ($SCHEDULE, $TIMEZONE)"
