#!/usr/bin/env bash
set -e
NS=infra-hub
PROJECT=mcp-infra-hub-507109
GSA="infra-hub-gsa@${PROJECT}.iam.gserviceaccount.com"

gcloud container clusters get-credentials infra-hub-test --location us-central1-a --project $PROJECT

kubectl create namespace $NS --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic db-credentials -n $NS \
  --from-literal=DB_USER=mcp_admin \
  --from-literal=DB_PASSWORD='supersecret' \
  --from-literal=DB_NAME=mcp_audit \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic ai-secrets -n $NS \
  --from-literal=GEMINI_API_KEY="$GEMINI_API_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create serviceaccount infra-hub-ksa -n $NS \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl annotate serviceaccount infra-hub-ksa -n $NS \
  iam.gke.io/gcp-service-account=$GSA --overwrite

kubectl apply -f k8s/
echo "Bootstrap complete. Waiting for pods..."
kubectl get pods -n $NS -w

