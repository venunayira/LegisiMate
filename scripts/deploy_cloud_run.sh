#!/usr/bin/env bash
set -euo pipefail

# One-command deployment to Google Cloud Run (works in Google Cloud Shell or locally with gcloud)
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-asia-south1}"
VERTEX_LOCATION="${VERTEX_LOCATION:-us-central1}"
GEMINI_MODEL="${GEMINI_MODEL:-gemini-2.5-flash}"
SERVICE_NAME="${SERVICE_NAME:-legisimate}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "Error: Set GOOGLE_CLOUD_PROJECT or run 'gcloud config set project <PROJECT_ID>' first." >&2
  exit 1
fi

echo "Enabling Cloud Run, Cloud Build, and Vertex AI APIs on project ${PROJECT_ID}..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  aiplatform.googleapis.com \
  --project="${PROJECT_ID}"

ENV_VARS="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},VERTEX_LOCATION=${VERTEX_LOCATION},GEMINI_MODEL=${GEMINI_MODEL}"
if [[ -n "${GEMINI_API_KEY:-}" ]]; then
  ENV_VARS="${ENV_VARS},GEMINI_API_KEY=${GEMINI_API_KEY}"
fi

echo "Deploying ${SERVICE_NAME} to Cloud Run (${REGION})..."
gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --platform=managed \
  --allow-unauthenticated \
  --memory=2Gi \
  --cpu=2 \
  --timeout=3600 \
  --max-instances=1 \
  --set-env-vars="${ENV_VARS}"

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')"
echo ""
echo "Deployed LegisiMate on Google Cloud Run:"
echo "  Live URL:   ${SERVICE_URL}"
echo "  Healthz:    ${SERVICE_URL}/healthz"
echo "  Workbench:  ${SERVICE_URL}/?case=c810d87708f94f318b01a2d80dc570e9"
