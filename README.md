# arxiv-upvote-trends

[![CI](https://github.com/susumuota/arxiv-upvote-trends/actions/workflows/ci.yaml/badge.svg)](https://github.com/susumuota/arxiv-upvote-trends/actions/workflows/ci.yaml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.14-blue)](https://www.python.org/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Collect trending papers from [alphaXiv](https://www.alphaxiv.org/) and [Hugging Face Daily Papers](https://huggingface.co/papers).

Fetches upvote counts and comment stats from both sources, aggregates them by arXiv ID, and uploads the results to a Hugging Face Dataset. Runs daily on Google Cloud Run Jobs with API response caching via GCS for resilience.

## Requirements

- Python >= 3.14
- [uv](https://docs.astral.sh/uv/)

## Setup

### Python

```bash
uv sync
source .venv/bin/activate
```

### Environment variables (.env)

Create `.env` based on `.env.sample` and set each variable.

```bash
cp .env.sample .env
# Edit the values in .env
source .env
```

### Hugging Face dataset (optional)

Setup steps for the Hugging Face Dataset repository used as the upload destination for the collected paper data.

Create a token with `write` permission on [Hugging Face Settings](https://huggingface.co/settings/tokens) and log in via the CLI:

```bash
hf auth login
```

Set the repository ID (e.g. `username/arxiv-upvote-trends`) to `HF_REPO_ID` in `.env`.
Omit `--private` to make the repository public.

```bash
hf repos create $HF_REPO_ID --type dataset --private
```

### Bluesky posting (optional)

Setup steps for posting the aggregated top papers to Bluesky. Create an app password in Bluesky settings.
For local runs, set the posting configuration in `.env`. For Cloud Run Jobs, store the app password in
Secret Manager and inject it as `BLUESKY_APP_PASSWORD`.
`post_to_bluesky()` reads `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD`, and `BLUESKY_SERVICE_URL` internally.

```bash
BLUESKY_HANDLE=your-handle.bsky.social
BLUESKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
BLUESKY_SERVICE_URL=https://bsky.social
```

If `BLUESKY_HANDLE` is empty or unset, the job skips posting.

### GCS bucket (optional)

Setup steps for using a GCS bucket to persist `fallback_cache`. If not needed, disable it with `unset GCS_BUCKET`.

To reuse an existing project, set `GOOGLE_CLOUD_PROJECT` in `.env` to that project ID and skip project creation.

```bash
gcloud projects list  # Check existing projects
# Set GOOGLE_CLOUD_PROJECT in .env to the existing project ID
```

To create a new project:

```bash
gcloud projects create $GOOGLE_CLOUD_PROJECT
```

Link a billing account:

```bash
gcloud billing accounts list
gcloud billing projects link $GOOGLE_CLOUD_PROJECT --billing-account=XXXXXX-XXXXXX-XXXXXX
# OK if billingEnabled: true
```

Create the GCS bucket:

```bash
REGION="us-central1"

gcloud services enable storage.googleapis.com --project="$GOOGLE_CLOUD_PROJECT"

gcloud storage buckets create "gs://$GCS_BUCKET" \
    --location="$REGION" \
    --uniform-bucket-level-access \
    --public-access-prevention \
    --project="$GOOGLE_CLOUD_PROJECT"
```

## Local Execution

### Run on the local machine

```bash
uv run --frozen --no-dev python main.py  # Run on the host
```

### Run in a local Docker container

```bash
IMAGE_NAME="arxiv-upvote-trends"

gcloud auth application-default login  # First time only

# 1 CPU, 1GB Memory, 10GB Disk, similar to Cloud Run Jobs free tier
# colima start -c 1 -m 1 -d 10

docker build -t "$IMAGE_NAME" .

docker run --rm --env-file .env \
  -v $HOME/.config/gcloud:/root/.config/gcloud:ro \
  "$IMAGE_NAME"
```

To enter a shell inside the container for debugging:

```bash
docker run --rm -it --env-file .env \
  -v $HOME/.config/gcloud:/root/.config/gcloud:ro \
  "$IMAGE_NAME" bash

uv run --frozen --no-dev python main.py  # Run inside the container
```

## Production Deployment (Cloud Run Jobs)

Before starting, complete the [GCS bucket (optional)](#gcs-bucket-optional) steps to create the GCP project and the GCS bucket.

### Artifact Registry

Create a repository. Configure a cleanup policy to keep only the latest image and stay within the free tier:

```bash
REPO_NAME="arxiv-upvote-trends"

gcloud services enable artifactregistry.googleapis.com --project="$GOOGLE_CLOUD_PROJECT"

gcloud artifacts repositories create "$REPO_NAME" \
    --repository-format=docker \
    --location="$REGION" \
    --project="$GOOGLE_CLOUD_PROJECT"

gcloud artifacts repositories list \
    --location="$REGION" \
    --project="$GOOGLE_CLOUD_PROJECT"

cat > cleanup-policy.json << 'EOF'
[
  {
    "name": "keep-latest",
    "action": { "type": "Keep" },
    "mostRecentVersions": {
      "keepCount": 1
    }
  }
]
EOF

gcloud artifacts repositories set-cleanup-policies "$REPO_NAME" \
    --location="$REGION" \
    --project="$GOOGLE_CLOUD_PROJECT" \
    --policy=cleanup-policy.json \
    --no-dry-run

rm cleanup-policy.json

gcloud artifacts repositories list-cleanup-policies "$REPO_NAME" \
    --location="$REGION" \
    --project="$GOOGLE_CLOUD_PROJECT"
```

### Cloud Build

Build and push the image:

```bash
IMAGE_NAME="arxiv-upvote-trends"

gcloud services enable cloudbuild.googleapis.com --project="$GOOGLE_CLOUD_PROJECT"

gcloud builds submit \
    --tag="${REGION}-docker.pkg.dev/${GOOGLE_CLOUD_PROJECT}/${REPO_NAME}/${IMAGE_NAME}" \
    --region="$REGION" \
    --project="$GOOGLE_CLOUD_PROJECT"

gcloud artifacts docker images list \
    "${REGION}-docker.pkg.dev/${GOOGLE_CLOUD_PROJECT}/${REPO_NAME}" \
    --project="$GOOGLE_CLOUD_PROJECT"
```

### Cloud Run Jobs

Create a service account, then create and execute the job:

```bash
SA_NAME="arxiv-upvote-trends-run"
JOB_NAME="arxiv-upvote-trends"

gcloud iam service-accounts create "$SA_NAME" \
    --project="$GOOGLE_CLOUD_PROJECT"

gcloud storage buckets add-iam-policy-binding "gs://$GCS_BUCKET" \
    --member="serviceAccount:${SA_NAME}@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"

gcloud services enable secretmanager.googleapis.com --project="$GOOGLE_CLOUD_PROJECT"

echo -n "$HF_TOKEN" | gcloud secrets create HF_TOKEN \
    --data-file=- \
    --project="$GOOGLE_CLOUD_PROJECT"

echo -n "$BLUESKY_APP_PASSWORD" | gcloud secrets create BLUESKY_APP_PASSWORD \
    --data-file=- \
    --project="$GOOGLE_CLOUD_PROJECT"

gcloud secrets add-iam-policy-binding HF_TOKEN \
    --member="serviceAccount:${SA_NAME}@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" \
    --project="$GOOGLE_CLOUD_PROJECT"

gcloud secrets add-iam-policy-binding BLUESKY_APP_PASSWORD \
    --member="serviceAccount:${SA_NAME}@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" \
    --project="$GOOGLE_CLOUD_PROJECT"

gcloud secrets describe HF_TOKEN --project="$GOOGLE_CLOUD_PROJECT"

gcloud services enable run.googleapis.com --project="$GOOGLE_CLOUD_PROJECT"

gcloud run jobs create "$JOB_NAME" \
    --image="${REGION}-docker.pkg.dev/${GOOGLE_CLOUD_PROJECT}/${REPO_NAME}/${IMAGE_NAME}" \
    --region="$REGION" \
    --project="$GOOGLE_CLOUD_PROJECT" \
    --service-account="${SA_NAME}@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com" \
    --set-env-vars="GCS_BUCKET=${GCS_BUCKET},HF_REPO_ID=${HF_REPO_ID},BLUESKY_HANDLE=${BLUESKY_HANDLE},BLUESKY_SERVICE_URL=${BLUESKY_SERVICE_URL}" \
    --set-secrets="HF_TOKEN=HF_TOKEN:latest,BLUESKY_APP_PASSWORD=BLUESKY_APP_PASSWORD:latest" \
    --max-retries=0 \
    --task-timeout=30m \
    --memory=1024Mi

gcloud run jobs list \
    --region="$REGION" \
    --project="$GOOGLE_CLOUD_PROJECT"

gcloud run jobs execute "$JOB_NAME" \
    --region="$REGION" \
    --project="$GOOGLE_CLOUD_PROJECT" \
    --async

gcloud run jobs executions list \
    --job="$JOB_NAME" \
    --region="$REGION" \
    --project="$GOOGLE_CLOUD_PROJECT"

gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=$JOB_NAME" \
    --project="$GOOGLE_CLOUD_PROJECT" \
    --limit=100 \
    --format="value(textPayload)" | tail -r
```

### Cloud Scheduler

Create a schedule that runs the job daily at 9:00 (JST):

```bash
SCHEDULE_NAME="arxiv-upvote-trends-schedule"

gcloud services enable cloudscheduler.googleapis.com --project="$GOOGLE_CLOUD_PROJECT"

gcloud run jobs add-iam-policy-binding "$JOB_NAME" \
    --member="serviceAccount:${SA_NAME}@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com" \
    --role="roles/run.invoker" \
    --region="$REGION" \
    --project="$GOOGLE_CLOUD_PROJECT"

gcloud scheduler jobs create http "${SCHEDULE_NAME}" \
    --location="$REGION" \
    --schedule="0 9 * * *" \
    --time-zone="Asia/Tokyo" \
    --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${GOOGLE_CLOUD_PROJECT}/jobs/${JOB_NAME}:run" \
    --http-method=POST \
    --oauth-service-account-email="${SA_NAME}@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com" \
    --project="$GOOGLE_CLOUD_PROJECT"

gcloud scheduler jobs list \
    --location="$REGION" \
    --project="$GOOGLE_CLOUD_PROJECT"

gcloud logging read "resource.type=cloud_scheduler_job" \
    --project="$GOOGLE_CLOUD_PROJECT" \
    --limit=100 | tail -r
```

## Development

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/).

```bash
# Test
pytest

# Lint & Format
ruff check .
ruff format .
```

### pre-commit

Git hooks are managed by [pre-commit](https://pre-commit.com/). Install the hooks after cloning:

```bash
uv run pre-commit install
```

The following hooks run automatically on `git commit`:

- **trailing-whitespace** / **end-of-file-fixer** — Whitespace cleanup
- **check-yaml** / **check-toml** — Syntax validation
- **check-added-large-files** — Prevent accidental large file commits
- **ruff check --fix** / **ruff format** — Lint and format
- **gitleaks** — Secret detection (HF tokens, GCP keys, etc.)
- **pytest** — Run tests

To run all hooks manually:

```bash
uv run pre-commit run --all-files
```

## License

[MIT](LICENSE)
