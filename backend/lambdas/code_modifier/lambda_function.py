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

MODIFY_PROMPT = """You are modifying an existing small application based on a user request.

Modification request:
{instruction}

Current project files:
{current_files}

Return ONLY valid JSON with this exact shape, nothing else:
{{
  "files": [
    {{"path": "app.py", "content": "full updated file contents"}}
  ]
}}

Rules:
- Only include files that changed or are new. Do not repeat unchanged files.
- Return full file contents for each changed file, not a diff.
- Keep the app runnable — no placeholder TODOs, no pseudocode.
- Do not include markdown fences around the JSON.
"""


def lambda_handler(event, context):
    body = event.get("body")
    if isinstance(body, str):
        body = json.loads(body)
    elif body is None:
        body = event

    project_id = body.get("project_id")
    instruction = body.get("instruction")
    if not project_id or not instruction:
        return _response(400, {"error": "project_id and instruction are required"})

    item = projects_table.get_item(Key={"project_id": project_id}).get("Item")
    if not item:
        return _response(404, {"error": "project not found"})

    current_files = {}
    for path in item.get("file_paths", []):
        obj = s3.get_object(Bucket=CODE_BUCKET, Key=f"{project_id}/{path}")
        current_files[path] = obj["Body"].read().decode("utf-8")

    files_blob = "\n\n".join(f"--- {p} ---\n{c}" for p, c in current_files.items())

    secret = get_secret(SECRET_NAME, REGION)
    api_key = secret["GEMINI_API_KEY"]

    try:
        result = call_gemini(
            MODIFY_PROMPT.format(instruction=instruction, current_files=files_blob),
            api_key,
            json_output=True
        )
    except Exception as e:
        return _response(502, {"error": f"modification failed: {e}"})

    changed_paths = []
    all_paths = set(item.get("file_paths", []))
    for f in result.get("files", []):
        s3.put_object(
            Bucket=CODE_BUCKET,
            Key=f"{project_id}/{f['path']}",
            Body=f["content"].encode("utf-8")
        )
        changed_paths.append(f["path"])
        all_paths.add(f["path"])

    projects_table.update_item(
        Key={"project_id": project_id},
        UpdateExpression="SET file_paths = :fp, #s = :status",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":fp": list(all_paths), ":status": "modified"}
    )

    return _response(200, {"project_id": project_id, "changed_files": changed_paths})


def _response(status, payload):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps(payload)
    }
