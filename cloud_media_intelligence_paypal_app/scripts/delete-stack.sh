#!/usr/bin/env bash
set -euo pipefail
: "${STACK_NAME:=cloud-media-intelligence-paypal}"
: "${AWS_REGION:=us-east-1}"
aws cloudformation delete-stack --region "$AWS_REGION" --stack-name "$STACK_NAME"
echo "Delete started for $STACK_NAME"
