import json
import os
import time
import boto3
from boto3.dynamodb.conditions import Key

REGION = os.environ.get("AWS_REGION", "us-east-1")
CLUSTER_NAME = os.environ["ECS_CLUSTER"]
DEPLOYMENTS_TABLE = os.environ["DEPLOYMENTS_TABLE"]

ecs = boto3.client("ecs", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)
deployments_table = dynamodb.Table(DEPLOYMENTS_TABLE)


def lambda_handler(event, context):
    body = event.get("body")
    if isinstance(body, str):
        body = json.loads(body)
    elif body is None:
        body = event

    project_id = body.get("project_id")
    if not project_id:
        return _response(400, {"error": "project_id is required"})

    history = deployments_table.query(
        KeyConditionExpression=Key("project_id").eq(project_id),
        ScanIndexForward=False,
        Limit=2
    ).get("Items", [])

    if len(history) < 2:
        return _response(400, {"error": "no previous deployment to roll back to"})

    current, previous = history[0], history[1]
    service_name = previous["service_name"]

    ecs.update_service(
        cluster=CLUSTER_NAME,
        service=service_name,
        taskDefinition=previous["task_definition_arn"],
        desiredCount=1
    )

    rollback_id = f"{project_id}-{int(time.time())}"
    deployments_table.put_item(Item={
        "project_id": project_id,
        "deployment_id": rollback_id,
        "image_uri": previous["image_uri"],
        "task_definition_arn": previous["task_definition_arn"],
        "revision": previous["revision"],
        "service_name": service_name,
        "status": "rolled_back",
        "rolled_back_from": current["deployment_id"],
        "deployed_at": int(time.time())
    })

    return _response(200, {
        "project_id": project_id,
        "rolled_back_to_revision": previous["revision"],
        "rollback_deployment_id": rollback_id
    })


def _response(status, payload):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps(payload)
    }
