#!/usr/bin/env bash
set -euo pipefail

: "${STACK_NAME:=cloud-media-intelligence-paypal}"
: "${AWS_REGION:=us-east-1}"
: "${PAYPAL_CLIENT_ID:?Set PAYPAL_CLIENT_ID}"
: "${PAYPAL_CLIENT_SECRET:?Set PAYPAL_CLIENT_SECRET}"
: "${PAYPAL_MODE:=sandbox}"
: "${PAYMENT_RECEIVER_EMAIL:=blarghtrill@gmail.com}"
: "${CORS_ORIGIN:=*}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
DEPLOY_BUCKET="${STACK_NAME}-artifacts-${ACCOUNT_ID}-${AWS_REGION}"

aws s3 mb "s3://${DEPLOY_BUCKET}" --region "$AWS_REGION" 2>/dev/null || true
aws s3 cp "$ROOT/.build/create_order.zip" "s3://${DEPLOY_BUCKET}/create_order.zip"
aws s3 cp "$ROOT/.build/capture_order.zip" "s3://${DEPLOY_BUCKET}/capture_order.zip"
aws s3 cp "$ROOT/.build/create_upload_url.zip" "s3://${DEPLOY_BUCKET}/create_upload_url.zip"
aws s3 cp "$ROOT/.build/start_processing.zip" "s3://${DEPLOY_BUCKET}/start_processing.zip"
aws s3 cp "$ROOT/.build/get_job.zip" "s3://${DEPLOY_BUCKET}/get_job.zip"
aws s3 cp "$ROOT/.build/process_media.zip" "s3://${DEPLOY_BUCKET}/process_media.zip"

aws cloudformation deploy \
  --region "$AWS_REGION" \
  --stack-name "$STACK_NAME" \
  --template-file "$ROOT/cloudformation/template.yaml" \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    PayPalClientId="$PAYPAL_CLIENT_ID" \
    PayPalClientSecret="$PAYPAL_CLIENT_SECRET" \
    PayPalMode="$PAYPAL_MODE" \
    PaymentReceiverEmail="$PAYMENT_RECEIVER_EMAIL" \
    DeploymentBucketName="$DEPLOY_BUCKET" \
    CorsOrigin="$CORS_ORIGIN"

aws cloudformation describe-stacks \
  --region "$AWS_REGION" \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs" \
  --output table
