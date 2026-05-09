import json
import os
import urllib.parse
import boto3

sfn = boto3.client("stepfunctions")
STATE_MACHINE_ARN = os.environ["STATE_MACHINE_ARN"]

def handler(event, context):
    """
    S3 event dispatcher.
    Starts one Step Functions execution per uploaded object.
    """
    executions = []
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        size = record["s3"]["object"].get("size", 0)

        # Avoid recursive processing if someone uploads generated JSON to the raw bucket.
        if key.endswith(".json") or key.startswith("_system/"):
            continue

        payload = {
            "bucket": bucket,
            "key": key,
            "size": size,
            "source_event": "s3:ObjectCreated"
        }

        response = sfn.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            input=json.dumps(payload)
        )
        executions.append(response["executionArn"])

    return {"started": executions}
