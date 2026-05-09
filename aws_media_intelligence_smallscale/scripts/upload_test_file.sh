#!/usr/bin/env bash
set -euo pipefail

STACK_NAME="${1:-media-intel-small}"
FILE_PATH="${2:-}"
REGION="${3:-us-east-1}"

if [[ -z "$FILE_PATH" || ! -f "$FILE_PATH" ]]; then
  echo "Usage: $0 <stack-name> <file-path> <region>"
  exit 1
fi

RAW_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='RawMediaBucket'].OutputValue" \
  --output text)

BASENAME="$(basename "$FILE_PATH")"
aws s3 cp "$FILE_PATH" "s3://$RAW_BUCKET/uploads/$BASENAME" --region "$REGION"

echo "Uploaded to s3://$RAW_BUCKET/uploads/$BASENAME"
echo "The S3 event will start the Step Functions workflow automatically."
