# Cloud Media Intelligence Platform — Small Scale AWS + PayPal App

A small-scale, non-mission-critical SaaS proof-of-concept where users choose a processing package, pay with PayPal, upload images/videos, and send the media into an AWS media intelligence pipeline.

## What it does

- Static website frontend
- PayPal Checkout flow
- API Gateway + Lambda backend
- DynamoDB job/payment tracking
- S3 presigned upload URLs
- S3 raw upload bucket and results bucket
- Step Functions orchestration scaffold
- Rekognition image labeling
- Transcribe speech-to-text starter workflow
- Comprehend NLP analysis starter workflow
- Safe output language: "risk indicators" and "human review recommended," not definitive claims that someone is lying/high/etc.

## Folder layout

```text
cloud_media_intelligence_paypal_app/
├── frontend/
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   └── config.example.js
├── backend/
│   ├── lambda/
│   │   ├── create_order/
│   │   ├── capture_order/
│   │   ├── create_upload_url/
│   │   ├── start_processing/
│   │   └── get_job/
│   └── shared/
├── cloudformation/
│   └── template.yaml
├── scripts/
│   ├── package-lambdas.sh
│   ├── deploy.sh
│   └── delete-stack.sh
└── docs/
    ├── architecture.mmd
    ├── pricing-model.md
    └── safety-notes.md
```

## Prerequisites

- AWS CLI configured
- Python 3.11+
- Bash shell
- PayPal developer app credentials
- An AWS account with permissions for CloudFormation, Lambda, API Gateway, DynamoDB, S3, Step Functions, IAM, Rekognition, Transcribe, and Comprehend

## Fast deploy

```bash
cd cloud_media_intelligence_paypal_app
cp frontend/config.example.js frontend/config.js

export STACK_NAME=cloud-media-intelligence-paypal
export AWS_REGION=us-east-1
export PAYPAL_CLIENT_ID="YOUR_PAYPAL_CLIENT_ID"
export PAYPAL_CLIENT_SECRET="YOUR_PAYPAL_CLIENT_SECRET"
export PAYPAL_MODE="sandbox"
export PAYMENT_RECEIVER_EMAIL="blarghtrill@gmail.com"

bash scripts/package-lambdas.sh
bash scripts/deploy.sh
```

After deploy, CloudFormation outputs:
- API base URL
- frontend bucket name
- raw upload bucket
- results bucket

Upload the frontend files to the static website bucket:

```bash
aws s3 sync frontend/ s3://YOUR_FRONTEND_BUCKET --delete
```

Then edit `frontend/config.js` with the deployed API URL and PayPal client ID.

## PayPal note

This app creates PayPal orders server-side and captures them after approval. Payments are intended for `blarghtrill@gmail.com`, but your PayPal business account configuration controls where funds settle. In sandbox mode, use sandbox buyer/seller accounts.

## Small-scale assumptions

This is intentionally practical and not overbuilt:
- API Gateway HTTP API
- Lambda Python functions
- DynamoDB single-table style job records
- S3 object storage
- Step Functions for orchestration
- No Cognito login by default
- No production subscription ledger
- No enterprise SLA
- No PHI/PII compliance guarantee

## Safety note

Automated media analysis should not claim to prove someone is lying, intoxicated, guilty, truthful, impaired, or emotionally certain. The app uses "signals," "risk indicators," and "human review recommended" language only.
