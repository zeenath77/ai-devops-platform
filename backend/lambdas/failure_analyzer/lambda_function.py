import json
import os
import time
import boto3
from gemini_client import call_gemini, get_secret

REGION = os.environ.get("AWS_REGION", "us-east-1")
SECRET_NAME = os.environ["GEMINI_SECRET_NAME"]
PIPELINE_RUNS_TABLE = os.environ["PIPELINE_RUNS_TABLE"]

dynamodb = boto3.resource("dynamodb", region_name=REGION)
pipeline_runs_table = dynamodb.Table(PIPELINE_RUNS_TABLE)

ANALYSIS_PROMPT = """You are analyzing a failed CI/CD pipeline stage. Here are the logs:

{logs}

Respond with ONLY valid JSON in this shape:
{{
  "failure_type": "one of: dependency_error, syntax_error, test_failure, docker_error, network_error, config_error, unknown",
  "root_cause": "one sentence, specific",
  "affected_stage": "e.g. build, test, docker, deploy",
  "suggested_fix": "one sentence, actionable",
  "is_transient": true or false,
  "confidence": 0-100
}}
"""


def lambda_handler(event, context):
    body = event.get("body")
    if isinstance(body, str):
        body = json.loads(body)
    elif body is None:
        body = event

    project_id = body.get("project_id")
    run_id = body.get("run_id")
    logs = body.get("logs", "")
    if not logs:
        return _response(400, {"error": "logs is required"})

    secret = get_secret(SECRET_NAME, REGION)
    api_key = secret["GEMINI_API_KEY"]

    try:
        analysis = call_gemini(ANALYSIS_PROMPT.format(logs=logs[:12000]), api_key, json_output=True)
    except Exception as e:
        return _response(502, {"error": f"analysis failed: {e}"})

    if project_id and run_id:
        pipeline_runs_table.update_item(
            Key={"project_id": project_id, "run_id": run_id},
            UpdateExpression="SET failure_analysis = :fa, updated_at = :t",
            ExpressionAttributeValues={":fa": analysis, ":t": int(time.time())}
        )

    return _response(200, analysis)


def _response(status, payload):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps(payload)
    }
