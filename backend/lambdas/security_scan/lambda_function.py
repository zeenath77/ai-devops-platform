import json
import os
import re
import boto3
from gemini_client import call_gemini, get_secret

REGION = os.environ.get("AWS_REGION", "us-east-1")
CODE_BUCKET = os.environ["CODE_BUCKET"]
PROJECTS_TABLE = os.environ["PROJECTS_TABLE"]
SECRET_NAME = os.environ["GEMINI_SECRET_NAME"]

s3 = boto3.client("s3", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)
projects_table = dynamodb.Table(PROJECTS_TABLE)

SECRET_PATTERNS = [
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key"),
    (re.compile(r"(?i)api[_-]?key\s*=\s*['\"][a-zA-Z0-9_\-]{16,}['\"]"), "hardcoded API key"),
    (re.compile(r"(?i)password\s*=\s*['\"][^'\"]{4,}['\"]"), "hardcoded password"),
    (re.compile(r"-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----"), "embedded private key"),
]

SUMMARY_PROMPT = """You are a security reviewer. Given this list of pattern-matched findings and the
project's dependency file contents, write a short security summary (3-5 sentences) and a
verdict of PASS or FAIL. FAIL only if there are real hardcoded secrets or clearly vulnerable
dependency pins. Findings:

{findings}

Dependency files:
{deps}
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

    findings = []
    deps_blob = ""
    for path in item.get("file_paths", []):
        obj = s3.get_object(Bucket=CODE_BUCKET, Key=f"{project_id}/{path}")
        content = obj["Body"].read().decode("utf-8")
        for pattern, label in SECRET_PATTERNS:
            if pattern.search(content):
                findings.append(f"{path}: possible {label}")
        if path in ("requirements.txt", "package.json"):
            deps_blob += f"\n--- {path} ---\n{content}"

    secret = get_secret(SECRET_NAME, REGION)
    api_key = secret["GEMINI_API_KEY"]

    try:
        summary = call_gemini(
            SUMMARY_PROMPT.format(findings="\n".join(findings) or "none", deps=deps_blob or "none"),
            api_key
        )
    except Exception as e:
        return _response(502, {"error": f"security scan failed: {e}"})

    verdict = "FAIL" if findings else ("FAIL" if "FAIL" in summary.upper() else "PASS")

    return _response(200, {
        "project_id": project_id,
        "verdict": verdict,
        "pattern_findings": findings,
        "summary": summary
    })


def _response(status, payload):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps(payload)
    }
