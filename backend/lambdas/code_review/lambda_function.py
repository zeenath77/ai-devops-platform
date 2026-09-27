import json
import os
import boto3
from gemini_client import call_gemini, get_secret

REGION = os.environ.get("AWS_REGION", "us-east-1")
CODE_BUCKET = os.environ["CODE_BUCKET"]
PROJECTS_TABLE = os.environ["PROJECTS_TABLE"]
SECRET_NAME = os.environ["GEMINI_SECRET_NAME"]

s3 = boto3.client("s3", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)
projects_table = dynamodb.Table(PROJECTS_TABLE)

REVIEW_PROMPT = """You are an AI code reviewer in a CI/CD pipeline gate. Review this project's files.

{files_blob}

Check for: bugs, missing error handling, hardcoded credentials or secrets, unused imports,
duplicate code, overly complex functions, obvious security issues.

Respond in plain text using exactly this format:

ISSUES FOUND: <number>
<for each issue: severity (CRITICAL/WARNING/INFO), file, one-line description>

FINAL VERDICT: APPROVE
or
FINAL VERDICT: APPROVE_WITH_CHANGES
or
FINAL VERDICT: REJECT

Use REJECT only for hardcoded secrets, critical bugs, or major security issues.
"""


def lambda_handler(event, context):
    body = event.get("body")
    if isinstance(body, str):
        body = json.loads(body)
    elif body is None:
        body = event

    project_id = body.get("project_id")
    if not project_id:
        return _response(400, {"error": "project_id is required"})

    item = projects_table.get_item(Key={"project_id": project_id}).get("Item")
    if not item:
        return _response(404, {"error": "project not found"})

    files_blob = ""
    for path in item.get("file_paths", []):
        obj = s3.get_object(Bucket=CODE_BUCKET, Key=f"{project_id}/{path}")
        files_blob += f"\n\n--- {path} ---\n{obj['Body'].read().decode('utf-8')}"

    secret = get_secret(SECRET_NAME, REGION)
    api_key = secret["GEMINI_API_KEY"]

    try:
        review_text = call_gemini(REVIEW_PROMPT.format(files_blob=files_blob), api_key)
    except Exception as e:
        return _response(502, {"error": f"review failed: {e}"})

    verdict = "REJECT"
    for line in review_text.splitlines():
        if "FINAL VERDICT:" in line:
            if "APPROVE_WITH_CHANGES" in line:
                verdict = "APPROVE_WITH_CHANGES"
            elif "APPROVE" in line:
                verdict = "APPROVE"
            elif "REJECT" in line:
                verdict = "REJECT"
            break

    return _response(200, {"project_id": project_id, "verdict": verdict, "review": review_text})


def _response(status, payload):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps(payload)
    }
