# AWS Media Intelligence Small-Scale CloudFormation Deployment

This project deploys a reasonably small, non-mission-critical AWS pipeline that:
- accepts uploaded images, videos, or audio into S3
- starts a Step Functions workflow automatically from S3 object creation
- runs Amazon Rekognition labels/faces for images and videos
- runs Amazon Transcribe for audio/video speech-to-text
- runs Amazon Comprehend sentiment, key phrases, entities, and repeated words on transcripts
- stores raw media, intermediate analysis JSON, transcripts, and final JSON results in S3
- stores searchable metadata in DynamoDB

Safety note: this stack does **not** declare someone is "lying" or "high." It stores safe outputs such as:
- `happy_appearance_signal`
- `stress_or_confusion_signal`
- `possible_contradiction_language_signal`
- `possible_intoxication_review_signal`
- `human_review_recommended`

These are review flags, not determinations.

## Folder layout

```text
aws_media_intelligence_smallscale/
├── cloudformation.yaml
├── lambda/
│   ├── dispatcher.py
│   └── processor.py
├── scripts/
│   ├── build_and_deploy.sh
│   ├── delete_stack.sh
│   └── upload_test_file.sh
└── docs/
    ├── architecture.mmd
    └── s3-layout.txt
```

## Prerequisites

- AWS CLI v2 configured with credentials
- Python 3.11+
- Bash shell
- An AWS region that supports Rekognition, Transcribe, Comprehend, Step Functions, Lambda, DynamoDB, and S3

## Deploy

```bash
cd aws_media_intelligence_smallscale
chmod +x scripts/*.sh

./scripts/build_and_deploy.sh \
  my-media-intel-small \
  us-east-1 \
  my-unique-artifact-bucket-name
```

The script zips the Lambda functions, uploads them to the artifact bucket, and deploys CloudFormation.

## Upload a test file

```bash
./scripts/upload_test_file.sh my-media-intel-small path/to/test.mp4 us-east-1
```

## View outputs

After deploy:

```bash
aws cloudformation describe-stacks \
  --stack-name my-media-intel-small \
  --region us-east-1 \
  --query "Stacks[0].Outputs"
```

Look in the FinalResultsBucket output for final JSON results.

## Cost warning

This is designed for low-volume testing. Rekognition Video and Transcribe can cost money per minute. Delete the stack when finished:

```bash
./scripts/delete_stack.sh my-media-intel-small us-east-1
```
