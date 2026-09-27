import json
import os
import time
import boto3
from boto3.dynamodb.conditions import Key

REGION = os.environ.get("AWS_REGION", "us-east-1")
PROJECTS_TABLE = os.environ["PROJECTS_TABLE"]
DEPLOYMENTS_TABLE = os.environ["DEPLOYMENTS_TABLE"]
PIPELINE_RUNS_TABLE = os.environ["PIPELINE_RUNS_TABLE"]
PROJECT_PREFIX = os.environ.get("PROJECT_PREFIX", "ai-devops")

dynamodb = boto3.resource("dynamodb", region_name=REGION)
projects_table = dynamodb.Table(PROJECTS_TABLE)
deployments_table = dynamodb.Table(DEPLOYMENTS_TABLE)
pipeline_runs_table = dynamodb.Table(PIPELINE_RUNS_TABLE)
lambda_client = boto3.client("lambda", region_name=REGION)


def _invoke(function_suffix, payload):
    resp = lambda_client.invoke(
        FunctionName=f"{PROJECT_PREFIX}-{function_suffix}",
        InvocationType="RequestResponse",
        Payload=json.dumps({"body": payload}).encode("utf-8")
    )
    result = json.loads(resp["Payload"].read())
    body = result.get("body")
    return json.loads(body) if isinstance(body, str) else result


def _invoke_async(function_suffix, payload):
    lambda_client.invoke(
        FunctionName=f"{PROJECT_PREFIX}-{function_suffix}",
        InvocationType="Event",
        Payload=json.dumps({"body": payload}).encode("utf-8")
    )


def lambda_handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "/")

    if method == "OPTIONS":
        return _response(200, {})

    raw_body = event.get("body")
    payload = json.loads(raw_body) if raw_body else {}

    if path == "/projects" and method == "GET":
        items = projects_table.scan().get("Items", [])
        return _response(200, {"projects": items})

    if path == "/projects" and method == "POST":
        prompt = payload.get("prompt")
        if not prompt:
            return _response(400, {"error": "prompt is required"})

        project_id = f"pending-{int(time.time())}"
        projects_table.put_item(Item={
            "project_id": project_id,
            "prompt": prompt,
            "file_paths": [],
            "created_at": int(time.time()),
            "status": "generating"
        })
        try:
            _invoke_async("code-generator", {"prompt": prompt, "project_id": project_id})
        except Exception as e:
            projects_table.update_item(
                Key={"project_id": project_id},
                UpdateExpression="SET #s = :s, error_message = :e",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":s": "failed", ":e": str(e)}
            )
            return _response(502, {"error": f"generation invoke failed: {e}"})
        return _response(202, {"project_id": project_id, "status": "generating"})

    if path.endswith("/modify") and method == "POST":
        project_id = path.split("/")[-2]
        payload["project_id"] = project_id
        try:
            result = _invoke("code-modifier", payload)
        except Exception as e:
            return _response(502, {"error": f"modification invoke failed: {e}"})
        return _response(200, result)

    if path.endswith("/rollback") and method == "POST":
        project_id = path.split("/")[-2]
        payload["project_id"] = project_id
        try:
            result = _invoke("rollback", payload)
        except Exception as e:
            return _response(502, {"error": f"rollback invoke failed: {e}"})
        return _response(200, result)

    if path.startswith("/projects/") and method == "GET":
        project_id = path.split("/")[-1]
        item = projects_table.get_item(Key={"project_id": project_id}).get("Item")
        if not item:
            return _response(404, {"error": "not found"})
        return _response(200, item)

    if path.startswith("/deployments/") and method == "GET":
        project_id = path.split("/")[-1]
        items = deployments_table.query(
            KeyConditionExpression=Key("project_id").eq(project_id),
            ScanIndexForward=False
        ).get("Items", [])
        return _response(200, {"deployments": items})

    if path.startswith("/pipeline-runs/") and method == "GET":
        project_id = path.split("/")[-1]
        items = pipeline_runs_table.query(
            KeyConditionExpression=Key("project_id").eq(project_id),
            ScanIndexForward=False
        ).get("Items", [])
        return _response(200, {"runs": items})

    if path == "/metrics" and method == "GET":
        runs = pipeline_runs_table.scan().get("Items", [])
        total = len(runs)
        succeeded = len([r for r in runs if r.get("status") == "success"])
        failed = len([r for r in runs if r.get("status") == "failed"])
        success_rate = round((succeeded / total) * 100, 1) if total else 0
        return _response(200, {
            "total_runs": total,
            "succeeded": succeeded,
            "failed": failed,
            "success_rate": success_rate
        })

    return _response(404, {"error": "route not found"})


def _response(status, payload):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            "Access-Control-Allow-Headers": "content-type"
        },
        "body": json.dumps(payload, default=str)
    }