import json
import os
import boto3
from gemini_client import call_gemini, get_secret

REGION = os.environ.get("AWS_REGION", "us-east-1")
CODE_BUCKET = os.environ["CODE_BUCKET"]
PROJECTS_TABLE = os.environ["PROJECTS_TABLE"]
SECRET_NAME = os.environ["GEMINI_SECRET_NAME"]
MAX_ATTEMPTS = 3

s3 = boto3.client("s3", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)
projects_table = dynamodb.Table(PROJECTS_TABLE)

FIX_PROMPT = """A CI/CD pipeline build failed for this project. Fix the code.

Error / logs:
{error_log}

Current files:
{files_blob}

Return ONLY valid JSON in this shape:
{{
  "files": [
    {{"path": "app.py", "content": "full corrected file contents"}}
  ],
  "explanation": "one sentence on what was wrong and what changed"
}}

Only include files that changed. Return full corrected contents for each, not a diff.
"""


def lambda_handler(event, context):
    body = event.get("body")
    if isinstance(body, str):
        body = json.loads(body)
    elif body is None:
        body = event

    project_id = body.get("project_id")
    error_log = body.get("error_log", "")
    attempt = int(body.get("attempt", 1))

    if not project_id or not error_log:
        return _response(400, {"error": "project_id and error_log are required"})

    if attempt > MAX_ATTEMPTS:
        return _response(200, {"project_id": project_id, "fixed": False, "reason": "max_attempts_reached"})

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
        result = call_gemini(
            FIX_PROMPT.format(error_log=error_log[:8000], files_blob=files_blob),
            api_key,
            json_output=True
        )
    except Exception as e:
        return _response(502, {"error": f"auto-fix failed: {e}"})

    changed = []
    for f in result.get("files", []):
        s3.put_object(
            Bucket=CODE_BUCKET,
            Key=f"{project_id}/{f['path']}",
            Body=f["content"].encode("utf-8")
        )
        changed.append(f["path"])

    return _response(200, {
        "project_id": project_id,
        "fixed": True,
        "attempt": attempt,
        "changed_files": changed,
        "explanation": result.get("explanation", "")
    })


def _response(status, payload):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps(payload)
    }
