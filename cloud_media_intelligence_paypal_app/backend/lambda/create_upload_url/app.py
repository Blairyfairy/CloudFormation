import os
import re
import boto3
from common import response, parse_event, now_epoch

s3 = boto3.client("s3")
ddb = boto3.resource("dynamodb")
table = ddb.Table(os.environ["JOBS_TABLE"])

SAFE = re.compile(r"[^A-Za-z0-9._-]+")

def clean(name):
    return SAFE.sub("_", name)[:180]

def lambda_handler(event, context):
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return response(200, {})
    body = parse_event(event)
    job_id = body.get("jobId")
    filename = clean(body.get("filename", "upload.bin"))
    content_type = body.get("contentType") or "application/octet-stream"
    size = int(body.get("size") or 0)

    if not job_id:
        return response(400, {"error": "jobId required"})
    job = table.get_item(Key={"jobId": job_id}).get("Item")
    if not job or job.get("status") not in ["PAID", "UPLOAD_READY", "PROCESSING", "COMPLETE"]:
        return response(403, {"error": "Job not paid or not found"})

    key = f"raw/{job_id}/{filename}"
    url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": os.environ["RAW_BUCKET"], "Key": key, "ContentType": content_type},
        ExpiresIn=900
    )
    table.update_item(
        Key={"jobId": job_id},
        UpdateExpression="SET #s=:s, updatedAt=:u",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": "UPLOAD_READY", ":u": now_epoch()}
    )
    return response(200, {"uploadUrl": url, "s3Key": key, "maxAgeSeconds": 900, "sizeReceived": size})
