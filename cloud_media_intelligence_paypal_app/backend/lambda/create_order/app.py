import os
import boto3
from common import response, parse_event, PLANS, new_job_id, now_epoch, decimalize
from paypal_client import paypal_request

ddb = boto3.resource("dynamodb")
table = ddb.Table(os.environ["JOBS_TABLE"])

def lambda_handler(event, context):
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return response(200, {})
    body = parse_event(event)
    plan_id = body.get("planId")
    if plan_id not in PLANS:
        return response(400, {"error": "Invalid planId", "validPlans": list(PLANS.keys())})
    plan = PLANS[plan_id]
    job_id = new_job_id()

    order = paypal_request("/v2/checkout/orders", payload={
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": job_id,
            "description": f"{plan['name']} media processing package",
            "custom_id": job_id,
            "amount": {"currency_code": "USD", "value": plan["price"]},
            "payee": {"email_address": os.environ.get("PAYMENT_RECEIVER_EMAIL", "blarghtrill@gmail.com")}
        }]
    })

    table.put_item(Item=decimalize({
        "jobId": job_id,
        "status": "PAYMENT_CREATED",
        "planId": plan_id,
        "plan": plan,
        "paypalOrderId": order["id"],
        "createdAt": now_epoch(),
        "updatedAt": now_epoch()
    }))

    return response(200, {"jobId": job_id, "orderId": order["id"]})
