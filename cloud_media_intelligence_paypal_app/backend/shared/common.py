import json
import os
import time
import uuid
from decimal import Decimal

PLANS = {
    "starter": {"name": "Starter", "price": "9.99", "images": 500, "videoMinutes": 10, "storageGb": 5},
    "basic": {"name": "Basic", "price": "24.99", "images": 2000, "videoMinutes": 30, "storageGb": 20},
    "pro": {"name": "Pro", "price": "49.99", "images": 5000, "videoMinutes": 100, "storageGb": 50},
    "business": {"name": "Business", "price": "99.99", "images": 15000, "videoMinutes": 300, "storageGb": 150},
}

def response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": os.environ.get("CORS_ORIGIN", "*"),
            "Access-Control-Allow-Headers": "content-type,authorization",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS"
        },
        "body": json.dumps(body, default=str)
    }

def parse_event(event):
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return {}
    body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        import base64
        body = base64.b64decode(body).decode("utf-8")
    return json.loads(body)

def new_job_id():
    return "job_" + uuid.uuid4().hex[:24]

def now_epoch():
    return int(time.time())

def decimalize(obj):
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: decimalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [decimalize(v) for v in obj]
    return obj
