# Build and run instructions for the Daily Digest App

## Local Development

### Prerequisites
- Python 3.11+
- Docker (optional, for containerized run)
- API keys:
  - DeepSeek API key
  - News API key
  - Google service account JSON (for Drive integration)

### Setup

1. Copy environment template:
```bash
cp .env.example .env
```

2. Fill in your API keys in `.env`:
```
DEEPSEEK_API_KEY=your_key_here
NEWSAPI_KEY=your_key_here
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
GOOGLE_DRIVE_FOLDER_ID=your_drive_folder_id
```

3. Create credentials directory and add service account JSON:
```bash
mkdir -p credentials
cp /path/to/your/service-account.json credentials/google-service-account.json
```

4. Create data directory for artifacts:
```bash
mkdir -p data
```

### Running Locally (without Docker)

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run single digest:
```bash
RUN_MODE=once python -m src.runtime.entrypoint
```

3. Start scheduler:
```bash
RUN_MODE=scheduler python -m src.runtime.entrypoint
```

### Resilience Controls

The pipeline now includes explicit runtime guardrails:

- `MAX_RUN_SECONDS`: hard timeout for a single run in `RUN_MODE=once`
- `MAX_RETRIES`: retry budget for transient HTTP failures (timeouts, 429, 5xx)
- Circuit breakers per endpoint to prevent repeated failing calls from cascading
- Summarizer budget guardrails (`COST_LIMIT_USD`, `TOKEN_BUDGET`) with explicit logs

Recommended production defaults:

```bash
MAX_RETRIES=2
MAX_RUN_SECONDS=300
COST_LIMIT_USD=0.05
TOKEN_BUDGET=10000
```

### Running with Docker Compose

Prerequisites:
- Run `python setup_google_oauth.py` once on host so `credentials/google-oauth-token.json` exists.
- Keep `credentials/google-oauth-token.json` writable so token refresh can persist updates.

1. Build and start scheduler:
```bash
docker compose up -d digest
```

2. View logs:
```bash
docker compose logs -f digest
```

3. Run one-off digest:
```bash
docker compose run --rm digest_once
```

4. Stop scheduler:
```bash
docker compose down
```

## Production Deployment

This section covers production-ready deployment patterns for running the digest pipeline reliably with external scheduling.

### Build & Tag Image

```bash
docker build -t daily-digest:1.0 .
docker tag daily-digest:1.0 your-registry/daily-digest:1.0
docker push your-registry/daily-digest:1.0
```

### Production Topology

The recommended production architecture is **stateless job container + external scheduler**:
- Container runs in `RUN_MODE=once` (default in production image)
- External orchestrator (Kubernetes CronJob, Cloud Scheduler, systemd timer) triggers the container daily
- Container exits cleanly after completion
- Logs and artifacts are persisted to mounted volumes or cloud storage

**Benefits:**
- Stateless: no in-process scheduler keeping state
- Recoverable: failed runs are retried by the orchestrator
- Scalable: same image runs anywhere (laptop, VM, Kubernetes, serverless)
- Observable: exit codes, runtime, logs are owned by the orchestrator

### Option A: Kubernetes CronJob

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: daily-digest
spec:
  schedule: "0 7 * * *"  # 7:00 UTC daily
  jobTemplate:
    spec:
      backoffLimit: 2
      template:
        spec:
          serviceAccountName: digest-account
          containers:
          - name: digest
            image: your-registry/daily-digest:1.0
            imagePullPolicy: IfNotPresent
            env:
            - name: RUN_MODE
              value: "once"
            - name: DEEPSEEK_API_KEY
              valueFrom:
                secretKeyRef:
                  name: deepseek-creds
                  key: api-key
            - name: NEWSAPI_KEY
              valueFrom:
                secretKeyRef:
                  name: news-creds
                  key: api-key
            - name: GITHUB_TOKEN
              valueFrom:
                secretKeyRef:
                  name: github-creds
                  key: token
            - name: GOOGLE_DRIVE_FOLDER_ID
              valueFrom:
                configMapKeyRef:
                  name: digest-config
                  key: drive-folder-id
            volumeMounts:
            - name: data
              mountPath: /app/data
            - name: oauth-token
              mountPath: /app/credentials/google-oauth-token.json
              subPath: google-oauth-token.json
            - name: oauth-client
              mountPath: /app/credentials/google-oauth-client.json
              subPath: google-oauth-client.json
              readOnly: true
            resources:
              requests:
                cpu: 250m
                memory: 512Mi
              limits:
                cpu: 500m
                memory: 1Gi
            livenessProbe:
              exec:
                command:
                - /bin/sh
                - -c
                - test -f /app/data/digest_$(date +%Y-%m-%d).pdf || exit 0
              initialDelaySeconds: 0
              periodSeconds: 0
          restartPolicy: Never
          volumes:
          - name: data
            persistentVolumeClaim:
              claimName: digest-data
          - name: oauth-token
            secret:
              secretName: google-oauth-token
          - name: oauth-client
            secret:
              secretName: google-oauth-client
              defaultMode: 0444
```

Setup secrets:
```bash
kubectl create secret generic deepseek-creds --from-literal=api-key=sk-...
kubectl create secret generic news-creds --from-literal=api-key=pub_...
kubectl create secret generic github-creds --from-literal=token=ghp_...
kubectl create secret generic google-oauth-token --from-file=google-oauth-token.json
kubectl create secret generic google-oauth-client --from-file=google-oauth-client.json

kubectl create configmap digest-config --from-literal=drive-folder-id=1f80WOPKFPZXa65-ZhTUEEgNjg-0Tbo12

kubectl create pvc --storageclass standard --size 10Gi digest-data
```

### Option B: Google Cloud Scheduler + Cloud Run Jobs

For this project, `RUN_MODE=once` is a batch pattern, so Cloud Run Jobs is the preferred target.

#### Recommended (automated)

Use the included scripts:

```bash
# 1) Preflight checks (auth, project, APIs, secrets)
PROJECT_ID=YOUR_PROJECT \
REGION=asia-southeast1 \
./scripts/gcp_preflight.sh

# 1b) Bootstrap/rotate required secrets from local .env
PROJECT_ID=YOUR_PROJECT \
./scripts/setup_gcp_secrets.sh

# 2) Deploy/update Cloud Run Job + Scheduler trigger
PROJECT_ID=YOUR_PROJECT \
REGION=asia-southeast1 \
SCHEDULE="0 7 * * *" \
TIMEZONE="Asia/Hong_Kong" \
./scripts/deploy_gcp_cloud_run_job.sh

# Optional: run one immediate execution after deploy
PROJECT_ID=YOUR_PROJECT \
REGION=asia-southeast1 \
SCHEDULE="0 7 * * *" \
TIMEZONE="Asia/Hong_Kong" \
SMOKE_EXECUTE=true \
./scripts/deploy_gcp_cloud_run_job.sh

# Read-only status check (no deployment changes)
PROJECT_ID=YOUR_PROJECT \
REGION=asia-southeast1 \
./scripts/gcp_status_cloud_run_job.sh

# Operational health check (scheduler + latest execution + freshness)
PROJECT_ID=YOUR_PROJECT \
REGION=asia-southeast1 \
TIMEZONE="Asia/Hong_Kong" \
MAX_EXECUTION_AGE_HOURS=30 \
REQUIRE_EXPECTED_RUN=true \
./scripts/gcp_health_check.sh

`gcp_health_check.sh` now also validates that the latest scheduler attempt and latest execution are recent enough to satisfy the most recent expected cron window for simple daily schedules such as `0 7 * * *`. This catches the case where yesterday's run is still fresh enough to pass a 30-hour freshness check even though today's 07:00 run was missed.

# One-command release runner (preflight -> secrets -> deploy -> health)
PROJECT_ID=YOUR_PROJECT \
REGION=asia-southeast1 \
TIMEZONE="Asia/Hong_Kong" \
SCHEDULE="0 7 * * *" \
SMOKE_EXECUTE=true \
./scripts/gcp_release_run.sh

# Dry-run preview (no resource changes)
PROJECT_ID=YOUR_PROJECT \
REGION=asia-southeast1 \
DRY_RUN=true \
./scripts/gcp_release_run.sh
```

Important Drive auth note:
- Current Drive adapter refreshes OAuth token by writing to a local token file.
- For Cloud Run Jobs, prefer migrating to service-account based Drive access, or persist OAuth token state outside container filesystem (for example Secret Manager or Cloud Storage).

#### Manual (equivalent)

```bash
# 1. Build and push image to Artifact Registry
gcloud artifacts repositories create digest --repository-format=docker --location=asia-southeast1 2>/dev/null || true
gcloud auth configure-docker asia-southeast1-docker.pkg.dev --quiet
docker build -t asia-southeast1-docker.pkg.dev/YOUR_PROJECT/digest/daily-digest:1.0 .
docker push asia-southeast1-docker.pkg.dev/YOUR_PROJECT/digest/daily-digest:1.0

# 2. Create service accounts (idempotent)
gcloud iam service-accounts create digest-runner --display-name "Digest Job Runner" 2>/dev/null || true
gcloud iam service-accounts create cloud-scheduler-digest --display-name "Cloud Scheduler for Digest" 2>/dev/null || true

# 3. Grant permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT \
  --member serviceAccount:digest-runner@YOUR_PROJECT.iam.gserviceaccount.com \
  --role roles/secretmanager.secretAccessor --quiet

# Scheduler can invoke the Cloud Run Job
gcloud run jobs add-iam-policy-binding daily-digest \
  --region asia-southeast1 \
  --member serviceAccount:cloud-scheduler-digest@YOUR_PROJECT.iam.gserviceaccount.com \
  --role roles/run.invoker

# 4. Deploy Cloud Run Job
gcloud run jobs deploy daily-digest \
  --image asia-southeast1-docker.pkg.dev/YOUR_PROJECT/digest/daily-digest:1.0 \
  --region asia-southeast1 \
  --service-account digest-runner@YOUR_PROJECT.iam.gserviceaccount.com \
  --memory 512Mi \
  --cpu 1 \
  --max-retries 1 \
  --task-timeout 900s \
  --set-env-vars RUN_MODE=once,DIGEST_TZ=Asia/Hong_Kong \
  --set-secrets DEEPSEEK_API_KEY=deepseek-key:latest,NEWSAPI_KEY=newsapi-key:latest,GITHUB_TOKEN=github-token:latest

# 5. Create or update Scheduler HTTP trigger for the Job run endpoint
JOB_RUN_URI="https://run.googleapis.com/v2/projects/YOUR_PROJECT/locations/asia-southeast1/jobs/daily-digest:run"

gcloud scheduler jobs create http daily-digest \
  --location asia-southeast1 \
  --schedule "0 7 * * *" \
  --time-zone "Asia/Hong_Kong" \
  --uri "$JOB_RUN_URI" \
  --http-method POST \
  --oauth-service-account-email cloud-scheduler-digest@YOUR_PROJECT.iam.gserviceaccount.com \
  --oauth-token-scope https://www.googleapis.com/auth/cloud-platform \
  --message-body '{}' \
  --max-retry-attempts 1 \
  --min-backoff 300s \
  --max-backoff 3600s \
  2>/dev/null || \
gcloud scheduler jobs update http daily-digest \
  --location asia-southeast1 \
  --schedule "0 7 * * *" \
  --time-zone "Asia/Hong_Kong" \
  --uri "$JOB_RUN_URI" \
  --http-method POST \
  --oauth-service-account-email cloud-scheduler-digest@YOUR_PROJECT.iam.gserviceaccount.com \
  --oauth-token-scope https://www.googleapis.com/auth/cloud-platform \
  --message-body '{}'
```

### Option C: Systemd Timer (Linux/macOS Docker Desktop VM)

Create `/etc/systemd/system/digest-daily.service`:
```ini
[Unit]
Description=Daily AI Digest Pipeline
After=network.target

[Service]
Type=oneshot
WorkingDirectory=/path/to/Multi-Agent Experiment
ExecStart=/usr/bin/docker run --rm \
  -v /path/to/data:/app/data \
  -v /path/to/credentials/google-oauth-token.json:/app/credentials/google-oauth-token.json \
  -v /path/to/credentials/google-oauth-client.json:/app/credentials/google-oauth-client.json:ro \
  -e RUN_MODE=once \
  -e DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY} \
  -e NEWSAPI_KEY=${NEWSAPI_KEY} \
  -e GITHUB_TOKEN=${GITHUB_TOKEN} \
  daily-digest:1.0

StandardOutput=journal
StandardError=journal
```

Create `/etc/systemd/system/digest-daily.timer`:
```ini
[Unit]
Description=Daily Digest Scheduler
Requires=digest-daily.service

[Timer]
OnCalendar=*-*-* 07:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable digest-daily.timer
sudo systemctl start digest-daily.timer
sudo systemctl status digest-daily.timer
```

### Option D: AWS ECS Scheduled Task

```bash
# 1. Push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com
docker tag daily-digest:1.0 YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/daily-digest:1.0
docker push YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/daily-digest:1.0

# 2. Create ECS task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json

# 3. Create EventBridge rule (CloudWatch Events) for scheduling
aws events put-rule --name digest-daily --schedule-expression "cron(0 7 * * ? *)"
aws events put-targets --rule digest-daily --targets "Id"="1","Arn"="arn:aws:ecs:us-east-1:YOUR_ACCOUNT:cluster/default","RoleArn"="arn:aws:iam::YOUR_ACCOUNT:role/ecsTaskExecutionRole","EcsParameters"="{\"TaskDefinitionArn\":\"arn:aws:ecs:us-east-1:YOUR_ACCOUNT:task-definition/daily-digest:1\",\"LaunchType\":\"FARGATE\"}"
```

### Monitoring & Observability

All deployment options write logs to:
- `docker logs` / Kubernetes logs / systemd journal (runtime output)
- `/app/data/digest_YYYY-MM-DD.{md,html,pdf}` (local fallback artifacts when Drive upload fails)
- `/app/data/traces/run_*.jsonl` (run traces with phases, costs, tokens)

**Health Check (all platforms):**
Monitor for successful completion by checking:
1. Exit code = 0 (success) or 1 (failure, but artifacts may still be written)
2. Recent file modification in `data/` directory
3. Google Drive folder for new digest files named `Daily AI and Technology Digest - YYYY-MM-DD.pdf`

**Cost Monitoring:**
Each run logs `cost_usd` in the traces. Aggregate across runs to track monthly spend:
- Expected after Phase 1 optimizations: ~$0.0047/run
- Annual cost (daily): ~$1.72 USD

## Monitoring and Logs

Logs are written to:
- stdout (container logs captured by platform)
- `./data/traces/` (local artifacts)
- `./data/digest_YYYY-MM-DD.md` (fallback markdown digests)

## Testing and CI

Run tests locally:

```bash
pytest -q
```

Run lint/format checks locally:

```bash
ruff check src tests
black --check src tests
```

GitHub Actions workflow file:
- `.github/workflows/test-and-validate.yml`

The workflow runs lint, tests with coverage gate, and Docker build validation on pushes and pull requests.

## Provider Switching

To switch LLM provider:

1. Update `.env`:
```bash
LLM_PROVIDER=openai  # or anthropic
OPENAI_API_KEY=your_key_here
```

2. No code changes needed! The app will use the OpenAI adapter.

3. Verify output format:
```bash
RUN_MODE=once python -m src.runtime.entrypoint
```

## Troubleshooting

### API Key errors:
```
Check that all required env vars are set in .env
```

### Drive upload failures:
```
Digests fall back to local ./data/digest_YYYY-MM-DD.md
Check credentials path and permissions
```

### Summarization failures:
```
Check DeepSeek API quota and rate limits
Increase cost budget if needed: COST_LIMIT_USD
```
