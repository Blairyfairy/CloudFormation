#!/usr/bin/env bash
set -euo pipefail

STACK_NAME="${1:-media-intel-small}"
REGION="${2:-us-east-1}"
ARTIFACT_BUCKET="${3:-}"

if [[ -z "$ARTIFACT_BUCKET" ]]; then
  echo "Usage: $0 <stack-name> <region> <artifact-bucket-name>"
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/.build"
mkdir -p "$BUILD_DIR"

echo "Creating artifact bucket if needed: $ARTIFACT_BUCKET"
if ! aws s3api head-bucket --bucket "$ARTIFACT_BUCKET" 2>/dev/null; then
  if [[ "$REGION" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "$ARTIFACT_BUCKET" --region "$REGION"
  else
    aws s3api create-bucket \
      --bucket "$ARTIFACT_BUCKET" \
      --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
  fi
fi

aws s3api put-public-access-block \
  --bucket "$ARTIFACT_BUCKET" \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

DISPATCHER_ZIP="$BUILD_DIR/dispatcher.zip"
PROCESSOR_ZIP="$BUILD_DIR/processor.zip"

rm -f "$DISPATCHER_ZIP" "$PROCESSOR_ZIP"

(cd "$ROOT_DIR/lambda" && zip -q "$DISPATCHER_ZIP" dispatcher.py)
(cd "$ROOT_DIR/lambda" && zip -q "$PROCESSOR_ZIP" processor.py)

DISPATCHER_KEY="media-intel-artifacts/$STACK_NAME/dispatcher.zip"
PROCESSOR_KEY="media-intel-artifacts/$STACK_NAME/processor.zip"

aws s3 cp "$DISPATCHER_ZIP" "s3://$ARTIFACT_BUCKET/$DISPATCHER_KEY" --region "$REGION"
aws s3 cp "$PROCESSOR_ZIP" "s3://$ARTIFACT_BUCKET/$PROCESSOR_KEY" --region "$REGION"

aws cloudformation deploy \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --template-file "$ROOT_DIR/cloudformation.yaml" \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    ProjectName="$STACK_NAME" \
    LambdaCodeBucket="$ARTIFACT_BUCKET" \
    DispatcherCodeKey="$DISPATCHER_KEY" \
    ProcessorCodeKey="$PROCESSOR_KEY"

echo ""
echo "Deployment complete."
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs" \
  --output table
