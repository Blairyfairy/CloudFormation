import os
import boto3
from common import response, parse_event, now_epoch, decimalize
from paypal_client import paypal_request

ddb = boto3.resource("dynamodb")
table = ddb.Table(os.environ["JOBS_TABLE"])

def lambda_handler(event, context):
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return response(200, {})
    body = parse_event(event)
    order_id = body.get("orderId")
    job_id = body.get("jobId")
    if not order_id or not job_id:
        return response(400, {"error": "orderId and jobId are required"})

    capture = paypal_request(f"/v2/checkout/orders/{order_id}/capture", payload={})
    status = capture.get("status", "UNKNOWN")
    table.update_item(
        Key={"jobId": job_id},
        UpdateExpression="SET #s=:s, paypalCapture=:c, updatedAt=:u",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues=decimalize({":s": "PAID" if status == "COMPLETED" else f"PAYPAL_{status}", ":c": capture, ":u": now_epoch()})
    )
    return response(200, {"jobId": job_id, "paymentStatus": status})
