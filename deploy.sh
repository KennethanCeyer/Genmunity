#!/usr/bin/env bash
set -e

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

PROJECT_ID="${GCP_PROJECT_ID:-kr-devsummit26icn-501}"
SERVICE_NAME="genmunity"
REGION="asia-northeast3"

echo "=== Deploying Genmunity (Google ADK + OpsAgent) to Cloud Run [$SERVICE_NAME] ==="
gcloud run deploy "$SERVICE_NAME" \
  --project "$PROJECT_ID" \
  --source . \
  --platform managed \
  --region "$REGION" \
  --allow-unauthenticated \
  --set-secrets GEMINI_API_KEY=gemini-api-key:latest,GOOGLE_API_KEY=gemini-api-key:latest,GMAIL_CREDENTIALS_JSON=gmail-credentials:latest \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --quiet

ENDPOINT=$(gcloud run services describe "$SERVICE_NAME" --project "$PROJECT_ID" --platform managed --region "$REGION" --format 'value(status.url)')
echo "Genmunity Cloud Run URL: $ENDPOINT"
