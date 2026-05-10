import os
import boto3
from common import response, parse_event, now_epoch, decimalize

sfn = boto3.client("stepfunctions")
ddb = boto3.resource("dynamodb")
table = ddb.Table(os.environ["JOBS_TABLE"])

def lambda_handler(event, context):
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return response(200, {})
    body = parse_event(event)
    job_id = body.get("jobId")
    files = body.get("files") or []
    if not job_id or not files:
        return response(400, {"error": "jobId and files required"})

    job = table.get_item(Key={"jobId": job_id}).get("Item")
    if not job or job.get("status") not in ["PAID", "UPLOAD_READY", "PROCESSING", "COMPLETE"]:
        return response(403, {"error": "Job not paid or not found"})

    execution = sfn.start_execution(
        stateMachineArn=os.environ["STATE_MACHINE_ARN"],
        name=job_id[:80],
        input=__import__("json").dumps({
            "jobId": job_id,
            "files": files,
            "rawBucket": os.environ["RAW_BUCKET"],
            "resultsBucket": os.environ["RESULTS_BUCKET"]
        })
    )

    table.update_item(
        Key={"jobId": job_id},
        UpdateExpression="SET #s=:s, files=:f, executionArn=:e, updatedAt=:u",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues=decimalize({":s": "PROCESSING", ":f": files, ":e": execution["executionArn"], ":u": now_epoch()})
    )
    return response(200, {"jobId": job_id, "status": "PROCESSING", "executionArn": execution["executionArn"]})
