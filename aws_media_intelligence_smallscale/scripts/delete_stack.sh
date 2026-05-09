#!/usr/bin/env bash
set -euo pipefail

STACK_NAME="${1:-media-intel-small}"
REGION="${2:-us-east-1}"

echo "Emptying stack-created buckets before deletion..."
OUTPUTS=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" --query "Stacks[0].Outputs" --output json)

for KEY in RawMediaBucket IntermediateBucket TranscriptBucket FinalResultsBucket; do
  BUCKET=$(echo "$OUTPUTS" | python3 -c "import sys,json; data=json.load(sys.stdin); print(next((x['OutputValue'] for x in data if x['OutputKey']=='$KEY'), ''))")
  if [[ -n "$BUCKET" ]]; then
    echo "Emptying s3://$BUCKET"
    aws s3 rm "s3://$BUCKET" --recursive --region "$REGION" || true
  fi
done

aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$REGION"
echo "Delete started."
