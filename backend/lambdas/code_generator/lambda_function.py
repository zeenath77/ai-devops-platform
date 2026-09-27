import json
import os
import time
import boto3
from gemini_client import call_gemini, get_secret

REGION = os.environ.get("AWS_REGION", "us-east-1")
CODE_BUCKET = os.environ["CODE_BUCKET"]
PROJECTS_TABLE = os.environ["PROJECTS_TABLE"]
SECRET_NAME = os.environ["GEMINI_SECRET_NAME"]

s3 = boto3.client("s3", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)
projects_table = dynamodb.Table(PROJECTS_TABLE)

GENERATION_PROMPT = """You are a senior software engineer generating a small, working application.

User request:
{prompt}

Return ONLY valid JSON with this exact shape, nothing else:
{{
  "project_name": "short-kebab-case-name",
  "stack": "one line describing frontend/backend/db choices",
  "description": "one paragraph describing the app",
  "files": [
    {{"path": "app.py", "content": "full file contents as a string"}},
    {{"path": "requirements.txt", "content": "..."}},
    {{"path": "Dockerfile", "content": "..."}},
    {{"path": "test_app.py", "content": "..."}},
    {{"path": "README.md", "content": "..."}}
  ]
}}

Rules:
- Prefer Python + Flask or FastAPI for the backend unless the prompt clearly asks for something else.
- Always include a Dockerfile that runs the app on port 8080.
- Always include at least one test file using pytest.
- Keep the app small but genuinely runnable — no placeholder TODOs, no pseudocode.
- Do not include markdown fences around the JSON.
"""


def lambda_handler(event, context):
    body = event.get("body")
    if isinstance(body, str):
        body = json.loads(body)
    elif body is None:
        body = event

    prompt = body.get("prompt")
    project_id = body.get("project_id") or f"project-{int(time.time())}"
    if not prompt:
        return _response(400, {"error": "prompt is required"})

    secret = get_secret(SECRET_NAME, REGION)
    api_key = secret["GEMINI_API_KEY"]

    try:
        result = call_gemini(GENERATION_PROMPT.format(prompt=prompt), api_key, json_output=True)
    except Exception as e:
        projects_table.update_item(
            Key={"project_id": project_id},
            UpdateExpression="SET #s = :s, error_message = :e",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "failed", ":e": str(e)}
        )
        return _response(502, {"error": f"generation failed: {e}"})

    for f in result.get("files", []):
        s3.put_object(
            Bucket=CODE_BUCKET,
            Key=f"{project_id}/{f['path']}",
            Body=f["content"].encode("utf-8")
        )

    projects_table.put_item(Item={
        "project_id": project_id,
        "prompt": prompt,
        "stack": result.get("stack", ""),
        "description": result.get("description", ""),
        "file_paths": [f["path"] for f in result.get("files", [])],
        "created_at": int(time.time()),
        "status": "generated"
    })

    return _response(200, {
        "project_id": project_id,
        "stack": result.get("stack"),
        "description": result.get("description"),
        "files": [f["path"] for f in result.get("files", [])]
    })


def _response(status, payload):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps(payload)
    }
