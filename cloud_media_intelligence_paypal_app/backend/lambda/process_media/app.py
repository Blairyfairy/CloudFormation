import os
import json
import boto3
from common import now_epoch, decimalize

s3 = boto3.client("s3")
rekognition = boto3.client("rekognition")
comprehend = boto3.client("comprehend")
ddb = boto3.resource("dynamodb")
table = ddb.Table(os.environ["JOBS_TABLE"])

IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff")
TEXT_EXT = (".txt", ".json", ".vtt", ".srt")
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm")
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".aac", ".flac")

def analyze_one(raw_bucket, results_bucket, job_id, item):
    key = item["s3Key"]
    lower = key.lower()
    result = {"sourceKey": key, "filename": item.get("filename"), "analysis": {}, "safetyNote": "Automated outputs are indicators only and require human review for sensitive conclusions."}

    if lower.endswith(IMAGE_EXT):
        labels = rekognition.detect_labels(
            Image={"S3Object": {"Bucket": raw_bucket, "Name": key}},
            MaxLabels=50,
            MinConfidence=60
        )
        result["analysis"]["rekognitionLabels"] = [
            {"name": x["Name"], "confidence": round(x["Confidence"], 2), "parents": [p["Name"] for p in x.get("Parents", [])]}
            for x in labels.get("Labels", [])
        ]
        try:
            faces = rekognition.detect_faces(
                Image={"S3Object": {"Bucket": raw_bucket, "Name": key}},
                Attributes=["ALL"]
            )
            result["analysis"]["faceAttributes"] = [{
                "boundingBox": f.get("BoundingBox"),
                "emotions": sorted(
                    [{"type": e["Type"], "confidence": round(e["Confidence"], 2)} for e in f.get("Emotions", [])],
                    key=lambda x: x["confidence"], reverse=True
                )[:5],
                "pose": f.get("Pose"),
                "quality": f.get("Quality")
            } for f in faces.get("FaceDetails", [])]
        except Exception as exc:
            result["analysis"]["faceAttributesError"] = str(exc)

    elif lower.endswith(VIDEO_EXT + AUDIO_EXT):
        result["analysis"]["mediaWorkflow"] = "For small-scale starter deployment, uploaded video/audio is registered for async Transcribe/Rekognition Video/MediaConvert extension. See README for enabling job-specific async integrations."
        result["analysis"]["recommendedNextSteps"] = ["Start Transcribe job", "Start Rekognition Video label detection", "Optionally trigger MediaConvert"]

    else:
        result["analysis"]["note"] = "Unsupported file type for automated analysis in starter processor."

    out_key = f"results/{job_id}/{key.split('/')[-1]}.analysis.json"
    s3.put_object(Bucket=results_bucket, Key=out_key, Body=json.dumps(result, indent=2).encode("utf-8"), ContentType="application/json")
    return out_key

def lambda_handler(event, context):
    job_id = event["jobId"]
    raw_bucket = event["rawBucket"]
    results_bucket = event["resultsBucket"]
    files = event.get("files") or []
    result_keys = [analyze_one(raw_bucket, results_bucket, job_id, f) for f in files]

    table.update_item(
        Key={"jobId": job_id},
        UpdateExpression="SET #s=:s, resultKeys=:r, updatedAt=:u",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues=decimalize({":s": "COMPLETE", ":r": result_keys, ":u": now_epoch()})
    )
    return {"jobId": job_id, "status": "COMPLETE", "resultKeys": result_keys}
