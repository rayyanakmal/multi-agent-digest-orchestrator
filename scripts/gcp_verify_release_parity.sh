#!/usr/bin/env bash
set -euo pipefail

# Verify release/version parity across local git, GitHub, Cloud Run job config,
# and local Docker image cache.
#
# Usage:
#   PROJECT_ID=daily-digest-app-495805 REGION=asia-southeast1 ./scripts/gcp_verify_release_parity.sh
#
# Optional env vars:
#   JOB_NAME=daily-digest
#   BRANCH=main
#   REQUIRE_CLEAN_WORKTREE=true
#   REQUIRE_LOCAL_DOCKER_IMAGE=true
#   EXPECTED_APP_VERSION=2e81edf

PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-asia-southeast1}"
JOB_NAME="${JOB_NAME:-daily-digest}"
BRANCH="${BRANCH:-main}"
REQUIRE_CLEAN_WORKTREE="${REQUIRE_CLEAN_WORKTREE:-true}"
REQUIRE_LOCAL_DOCKER_IMAGE="${REQUIRE_LOCAL_DOCKER_IMAGE:-true}"
EXPECTED_APP_VERSION="${EXPECTED_APP_VERSION:-}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "[ERROR] PROJECT_ID is required"
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "[ERROR] git not found"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "[WARN] docker not found; local image parity checks will be skipped"
  REQUIRE_LOCAL_DOCKER_IMAGE="false"
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

LOCAL_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
LOCAL_SHA_FULL="$(git rev-parse HEAD)"
LOCAL_SHA_SHORT="$(git rev-parse --short HEAD)"

if [[ "$LOCAL_BRANCH" != "$BRANCH" ]]; then
  echo "[WARN] Local branch differs from target branch: local=$LOCAL_BRANCH target=$BRANCH"
fi

if [[ "$REQUIRE_CLEAN_WORKTREE" == "true" ]]; then
  if [[ -n "$(git status --porcelain)" ]]; then
    echo "[ERROR] Working tree is not clean"
    git status --short
    exit 1
  fi
  echo "[OK] Working tree is clean"
else
  echo "[WARN] Skipping clean-worktree requirement"
fi

REMOTE_SHA_FULL="$(git ls-remote origin "refs/heads/$BRANCH" | awk '{print $1}' | head -n1)"
if [[ -z "$REMOTE_SHA_FULL" ]]; then
  echo "[ERROR] Could not resolve origin/$BRANCH"
  exit 1
fi
REMOTE_SHA_SHORT="${REMOTE_SHA_FULL:0:7}"

echo "[INFO] Local git:  $LOCAL_SHA_FULL"
echo "[INFO] GitHub $BRANCH: $REMOTE_SHA_FULL"

if [[ "$LOCAL_SHA_FULL" != "$REMOTE_SHA_FULL" ]]; then
  echo "[ERROR] Local commit does not match GitHub branch head"
  exit 1
fi
echo "[OK] Local commit matches GitHub branch head"

JOB_JSON="$($GCLOUD_BIN run jobs describe "$JOB_NAME" --region "$REGION" --format=json)"

CLOUD_FIELDS="$(JOB_JSON="$JOB_JSON" python3 - <<'PY'
import json
import os

data = json.loads(os.environ["JOB_JSON"])

def pick_image(d):
    paths = [
        ("spec", "template", "spec", "template", "spec", "containers", 0, "image"),
        ("template", "template", "containers", 0, "image"),
    ]
    for path in paths:
        cur = d
        try:
            for key in path:
                cur = cur[key]
            if cur:
                return cur
        except Exception:
            pass
    return ""

def pick_app_version(d):
    env = (
        d.get("spec", {})
         .get("template", {})
         .get("spec", {})
         .get("template", {})
         .get("spec", {})
         .get("containers", [{}])[0]
         .get("env", [])
    )
    for item in env:
        if item.get("name") == "APP_VERSION":
            return item.get("value", "")
    return ""

print(pick_image(data))
print(pick_app_version(data))
PY
 )"

CLOUD_IMAGE="$(printf '%s' "$CLOUD_FIELDS" | sed -n '1p')"
CLOUD_APP_VERSION="$(printf '%s' "$CLOUD_FIELDS" | sed -n '2p')"

if [[ -z "$CLOUD_IMAGE" ]]; then
  echo "[ERROR] Could not resolve Cloud Run job image"
  exit 1
fi

echo "[INFO] Cloud image: $CLOUD_IMAGE"
echo "[INFO] Cloud APP_VERSION: ${CLOUD_APP_VERSION:-<unset>}"

TARGET_VERSION="$LOCAL_SHA_SHORT"
if [[ -n "$EXPECTED_APP_VERSION" ]]; then
  TARGET_VERSION="$EXPECTED_APP_VERSION"
fi

if [[ -n "$CLOUD_APP_VERSION" && "$CLOUD_APP_VERSION" != "$TARGET_VERSION" ]]; then
  echo "[ERROR] Cloud APP_VERSION mismatch: cloud=$CLOUD_APP_VERSION expected=$TARGET_VERSION"
  exit 1
fi

if [[ -z "$CLOUD_APP_VERSION" ]]; then
  echo "[WARN] APP_VERSION is not set in Cloud Run job; commit-level parity is partial"
else
  echo "[OK] Cloud APP_VERSION matches expected version"
fi

if [[ "$REQUIRE_LOCAL_DOCKER_IMAGE" == "true" ]]; then
  if ! docker image inspect "$CLOUD_IMAGE" >/dev/null 2>&1; then
    echo "[ERROR] Local Docker does not have deployed cloud image cached: $CLOUD_IMAGE"
    exit 1
  fi
  echo "[OK] Local Docker contains deployed cloud image"
else
  echo "[WARN] Skipping local docker image parity check"
fi

echo "[SUCCESS] Release parity verification passed"
echo "[INFO] Version anchor: $TARGET_VERSION"
