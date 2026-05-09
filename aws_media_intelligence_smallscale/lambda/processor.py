import json
import os
import re
import time
import uuid
from collections import Counter
from urllib.parse import unquote_plus

import boto3

s3 = boto3.client("s3")
rekognition = boto3.client("rekognition")
transcribe = boto3.client("transcribe")
comprehend = boto3.client("comprehend")
dynamodb = boto3.resource("dynamodb")

RAW_BUCKET = os.environ["RAW_BUCKET"]
INTERMEDIATE_BUCKET = os.environ["INTERMEDIATE_BUCKET"]
TRANSCRIPT_BUCKET = os.environ["TRANSCRIPT_BUCKET"]
FINAL_BUCKET = os.environ["FINAL_BUCKET"]
TABLE_NAME = os.environ["TABLE_NAME"]
LANGUAGE_CODE = os.environ.get("LANGUAGE_CODE", "en-US")

table = dynamodb.Table(TABLE_NAME)

IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp")
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".avi", ".mkv")
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg")


def handler(event, context):
    task = event.get("task")
    if not task:
        raise ValueError("Missing task")

    if task == "prepare":
        return prepare(event)
    if task == "analyze_image":
        return analyze_image(event)
    if task == "start_video_label_detection":
        return start_video_label_detection(event)
    if task == "check_video_label_detection":
        return check_video_label_detection(event)
    if task == "start_transcription":
        return start_transcription(event)
    if task == "check_transcription":
        return check_transcription(event)
    if task == "analyze_text":
        return analyze_text(event)
    if task == "aggregate":
        return aggregate(event)

    raise ValueError(f"Unknown task: {task}")


def prepare(event):
    key = unquote_plus(event["key"])
    ext = "." + key.rsplit(".", 1)[-1].lower() if "." in key else ""
    media_type = "unknown"
    if ext in IMAGE_EXT:
        media_type = "image"
    elif ext in VIDEO_EXT:
        media_type = "video"
    elif ext in AUDIO_EXT:
        media_type = "audio"

    item_id = str(uuid.uuid4())
    safe_prefix = f"items/{item_id}/"
    prepared = {
        **event,
        "item_id": item_id,
        "media_type": media_type,
        "prefix": safe_prefix,
        "created_epoch": int(time.time())
    }
    put_json(INTERMEDIATE_BUCKET, safe_prefix + "prepared.json", prepared)
    return prepared


def analyze_image(event):
    if event["media_type"] != "image":
        event["image_analysis"] = {"skipped": True, "reason": "not image"}
        return event

    bucket = event["bucket"]
    key = event["key"]
    labels = rekognition.detect_labels(
        Image={"S3Object": {"Bucket": bucket, "Name": key}},
        MaxLabels=40,
        MinConfidence=60
    )

    faces = rekognition.detect_faces(
        Image={"S3Object": {"Bucket": bucket, "Name": key}},
        Attributes=["ALL"]
    )

    result = {
        "labels": labels.get("Labels", []),
        "faces": faces.get("FaceDetails", []),
        "safe_interpretation": safe_face_interpretation(faces.get("FaceDetails", []))
    }
    put_json(INTERMEDIATE_BUCKET, event["prefix"] + "image_rekognition.json", result)
    event["image_analysis"] = {"written": event["prefix"] + "image_rekognition.json"}
    return event


def start_video_label_detection(event):
    if event["media_type"] != "video":
        event["video_label_job"] = {"skipped": True, "reason": "not video"}
        return event

    response = rekognition.start_label_detection(
        Video={"S3Object": {"Bucket": event["bucket"], "Name": event["key"]}},
        MinConfidence=60
    )
    event["video_label_job"] = {
        "job_id": response["JobId"],
        "status": "STARTED"
    }
    return event


def check_video_label_detection(event):
    job = event.get("video_label_job", {})
    if job.get("skipped"):
        return event

    response = rekognition.get_label_detection(
        JobId=job["job_id"],
        SortBy="TIMESTAMP"
    )
    status = response["JobStatus"]
    event["video_label_job"]["status"] = status

    if status == "SUCCEEDED":
        labels = response.get("Labels", [])
        # Small-scale version grabs first page. For production, paginate with NextToken.
        result = {"job_status": status, "labels": labels}
        put_json(INTERMEDIATE_BUCKET, event["prefix"] + "video_rekognition.json", result)
        event["video_analysis"] = {"written": event["prefix"] + "video_rekognition.json"}
    elif status == "FAILED":
        raise RuntimeError("Rekognition video label detection failed")

    return event


def start_transcription(event):
    if event["media_type"] not in ("video", "audio"):
        event["transcription_job"] = {"skipped": True, "reason": "not audio/video"}
        return event

    job_name = f"media-intel-{event['item_id']}"
    media_uri = f"s3://{event['bucket']}/{event['key']}"

    transcribe.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={"MediaFileUri": media_uri},
        LanguageCode=LANGUAGE_CODE,
        OutputBucketName=TRANSCRIPT_BUCKET,
        OutputKey=f"{event['prefix']}transcript.json",
        Settings={
            "ShowSpeakerLabels": True,
            "MaxSpeakerLabels": 4
        }
    )
    event["transcription_job"] = {
        "job_name": job_name,
        "status": "STARTED",
        "output_key": f"{event['prefix']}transcript.json"
    }
    return event


def check_transcription(event):
    job = event.get("transcription_job", {})
    if job.get("skipped"):
        return event

    response = transcribe.get_transcription_job(
        TranscriptionJobName=job["job_name"]
    )
    status = response["TranscriptionJob"]["TranscriptionJobStatus"]
    event["transcription_job"]["status"] = status

    if status == "COMPLETED":
        event["transcript"] = {
            "bucket": TRANSCRIPT_BUCKET,
            "key": job["output_key"]
        }
    elif status == "FAILED":
        reason = response["TranscriptionJob"].get("FailureReason", "Unknown")
        raise RuntimeError(f"Transcription failed: {reason}")

    return event


def analyze_text(event):
    transcript_text = ""
    if event.get("transcript"):
        obj = s3.get_object(Bucket=event["transcript"]["bucket"], Key=event["transcript"]["key"])
        transcript_json = json.loads(obj["Body"].read().decode("utf-8"))
        transcript_text = transcript_json.get("results", {}).get("transcripts", [{}])[0].get("transcript", "")

    if not transcript_text:
        event["text_analysis"] = {"skipped": True, "reason": "no transcript text"}
        return event

    # Comprehend sync APIs are size-limited. Keep small-scale deployment simple.
    text = transcript_text[:4500]
    sentiment = comprehend.detect_sentiment(Text=text, LanguageCode="en")
    phrases = comprehend.detect_key_phrases(Text=text, LanguageCode="en")
    entities = comprehend.detect_entities(Text=text, LanguageCode="en")
    repeated = repeated_words_and_phrases(transcript_text)

    result = {
        "sentiment": sentiment,
        "key_phrases": phrases.get("KeyPhrases", []),
        "entities": entities.get("Entities", []),
        "repeated_terms": repeated,
        "safe_language_flags": safe_language_flags(transcript_text, sentiment, repeated)
    }
    put_json(INTERMEDIATE_BUCKET, event["prefix"] + "comprehend_analysis.json", result)
    event["text_analysis"] = {"written": event["prefix"] + "comprehend_analysis.json"}
    return event


def aggregate(event):
    final = {
        "item_id": event["item_id"],
        "source": {"bucket": event["bucket"], "key": event["key"]},
        "media_type": event["media_type"],
        "created_epoch": event["created_epoch"],
        "outputs": {
            "intermediate_bucket": INTERMEDIATE_BUCKET,
            "transcript_bucket": TRANSCRIPT_BUCKET,
            "final_bucket": FINAL_BUCKET,
            "prefix": event["prefix"]
        },
        "analyses": {},
        "review_summary": {
            "human_review_recommended": False,
            "review_reasons": [],
            "important_note": "Risk flags are cues for human review only. They are not proof someone is lying, intoxicated, impaired, or truthful."
        }
    }

    for name, key in [
        ("image_rekognition", event["prefix"] + "image_rekognition.json"),
        ("video_rekognition", event["prefix"] + "video_rekognition.json"),
        ("comprehend_analysis", event["prefix"] + "comprehend_analysis.json"),
    ]:
        loaded = try_get_json(INTERMEDIATE_BUCKET, key)
        if loaded is not None:
            final["analyses"][name] = loaded

    add_review_flags(final)

    final_key = event["prefix"] + "final_result.json"
    put_json(FINAL_BUCKET, final_key, final)

    table.put_item(Item={
        "ItemId": event["item_id"],
        "SourceBucket": event["bucket"],
        "SourceKey": event["key"],
        "MediaType": event["media_type"],
        "FinalResultBucket": FINAL_BUCKET,
        "FinalResultKey": final_key,
        "HumanReviewRecommended": final["review_summary"]["human_review_recommended"],
        "CreatedEpoch": event["created_epoch"]
    })

    event["final_result"] = {"bucket": FINAL_BUCKET, "key": final_key}
    return event


def safe_face_interpretation(face_details):
    signals = []
    for idx, face in enumerate(face_details):
        emotions = sorted(face.get("Emotions", []), key=lambda x: x.get("Confidence", 0), reverse=True)
        top = emotions[0] if emotions else None
        signals.append({
            "face_index": idx,
            "top_expression_appearance": top,
            "note": "Expression appearance only; not a determination of actual emotion, truthfulness, or intoxication."
        })
    return signals


def repeated_words_and_phrases(text):
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    stop = {"the","and","for","that","this","with","you","are","was","were","have","has","had","not","but","from"}
    counts = Counter(w for w in words if w not in stop)
    return [{"term": k, "count": v} for k, v in counts.most_common(25) if v >= 2]


def safe_language_flags(text, sentiment, repeated):
    lower = text.lower()
    flags = []

    contradiction_markers = ["but", "however", "actually", "i never", "i did not", "that's not true", "no, "]
    if sum(lower.count(m) for m in contradiction_markers) >= 3:
        flags.append({
            "flag": "possible_contradiction_language_signal",
            "confidence": "low",
            "reason": "Multiple contradiction markers were found in the transcript."
        })

    if sentiment.get("Sentiment") in ("NEGATIVE", "MIXED"):
        flags.append({
            "flag": "stress_or_conflict_language_signal",
            "confidence": "low",
            "reason": f"Transcript sentiment was {sentiment.get('Sentiment')}."
        })

    intoxication_words = ["drunk", "high", "stoned", "intoxicated", "weed", "cocaine", "pills"]
    if any(w in lower for w in intoxication_words):
        flags.append({
            "flag": "possible_intoxication_review_signal",
            "confidence": "low",
            "reason": "Transcript contains substance-related words; human review required."
        })

    return flags


def add_review_flags(final):
    reasons = []

    comp = final["analyses"].get("comprehend_analysis", {})
    for flag in comp.get("safe_language_flags", []):
        reasons.append(flag)

    img = final["analyses"].get("image_rekognition", {})
    for face_signal in img.get("safe_interpretation", []):
        top = face_signal.get("top_expression_appearance") or {}
        if top.get("Type") in ("ANGRY", "CONFUSED", "SAD", "FEAR") and top.get("Confidence", 0) >= 75:
            reasons.append({
                "flag": "strong_expression_appearance_signal",
                "confidence": "medium",
                "reason": f"Face expression appearance returned {top.get('Type')} at {round(top.get('Confidence', 0), 2)}%."
            })

    if reasons:
        final["review_summary"]["human_review_recommended"] = True
        final["review_summary"]["review_reasons"] = reasons


def put_json(bucket, key, data):
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(data, default=str, indent=2).encode("utf-8"),
        ContentType="application/json"
    )


def try_get_json(bucket, key):
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        return json.loads(obj["Body"].read().decode("utf-8"))
    except s3.exceptions.NoSuchKey:
        return None
    except Exception:
        return None
