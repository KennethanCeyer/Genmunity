#!/usr/bin/env bash
set -e

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

PROJECT_ID="${GCP_PROJECT_ID:-kr-devsummit26icn-501}"
ADMIN_EMAIL="${MAIL_ADMIN_EMAIL:-devstar5011@gcplab.me}"
SERVICE_NAME="genmunity"
REGION="asia-northeast3"
PUBSUB_TOPIC="gmail-push-topic"
PUBSUB_SUB="gmail-push-cloudrun-sub"

echo "=== [1/3] Deploying Genmunity (Google ADK + OpsAgent) to Cloud Run [$SERVICE_NAME / $PROJECT_ID] ==="
gcloud run deploy "$SERVICE_NAME" \
  --project "$PROJECT_ID" \
  --source . \
  --platform managed \
  --region "$REGION" \
  --allow-unauthenticated \
  --set-env-vars "GCP_PROJECT_ID=${PROJECT_ID},GCP_USERNAME=${ADMIN_EMAIL},MAIL_ADMIN_EMAIL=${ADMIN_EMAIL},GCP_FIRSTNAME=Star,GCP_LASTNAME=Developer 5011,GENMUNITY_MODEL=gemini-4-argon,GENMUNITY_SECONDARY_MODEL=gemini-3.8-flash,GENMUNITY_BASE_URL=https://genmunity-858263435030.asia-northeast3.run.app" \
  --set-secrets GEMINI_API_KEY=gemini-api-key:latest,GOOGLE_API_KEY=gemini-api-key:latest,GMAIL_CREDENTIALS_JSON=gmail-credentials:latest,FORMS_CREDENTIALS_JSON=forms-credentials:latest \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --quiet

ENDPOINT=$(gcloud run services describe "$SERVICE_NAME" --project "$PROJECT_ID" --platform managed --region "$REGION" --format 'value(status.url)')
WEBHOOK_URL="${ENDPOINT}/gmail-webhook"
echo "Genmunity Cloud Run URL: $ENDPOINT"
echo "Gmail Pub/Sub Webhook URL: $WEBHOOK_URL"

echo "=== [2/3] Provisioning Cloud Pub/Sub Topic [projects/${PROJECT_ID}/topics/${PUBSUB_TOPIC}] ==="
gcloud pubsub topics create "$PUBSUB_TOPIC" --project "$PROJECT_ID" 2>/dev/null || true

gcloud pubsub topics add-iam-policy-binding "$PUBSUB_TOPIC" \
  --project "$PROJECT_ID" \
  --member="serviceAccount:gmail-api-push@system.gserviceaccount.com" \
  --role="roles/pubsub.publisher" >/dev/null

echo "=== [3/3] Binding Cloud Pub/Sub Push Subscription [${PUBSUB_SUB}] -> Cloud Run [${WEBHOOK_URL}] ==="
if gcloud pubsub subscriptions describe "$PUBSUB_SUB" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud pubsub subscriptions update "$PUBSUB_SUB" \
    --project "$PROJECT_ID" \
    --push-endpoint="$WEBHOOK_URL"
else
  gcloud pubsub subscriptions create "$PUBSUB_SUB" \
    --project "$PROJECT_ID" \
    --topic="$PUBSUB_TOPIC" \
    --push-endpoint="$WEBHOOK_URL" \
    --ack-deadline=60
fi

echo "=== Deployment & Pub/Sub -> Cloud Run Trigger Setup Complete ==="
echo "- Event Manager: Star Developer 5011 (${ADMIN_EMAIL})"
echo "- Assigned Project: ${PROJECT_ID}"
echo "- Pub/Sub Topic: projects/${PROJECT_ID}/topics/${PUBSUB_TOPIC}"
echo "- Push Endpoint: ${WEBHOOK_URL}"
echo "- Organizer Delegation: sniper45han@gmail.com, aristojeff@gmail.com"
