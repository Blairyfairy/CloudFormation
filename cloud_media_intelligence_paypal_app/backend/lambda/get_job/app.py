import os
import boto3
from common import response

ddb = boto3.resource("dynamodb")
table = ddb.Table(os.environ["JOBS_TABLE"])

def lambda_handler(event, context):
    job_id = (event.get("pathParameters") or {}).get("jobId")
    if not job_id:
        return response(400, {"error": "jobId required"})
    item = table.get_item(Key={"jobId": job_id}).get("Item")
    if not item:
        return response(404, {"error": "Job not found"})
    # Remove large PayPal details from public status
    item.pop("paypalCapture", None)
    return response(200, item)
