import json
import os
import time
import boto3

REGION = os.environ.get("AWS_REGION", "us-east-1")
CLUSTER_NAME = os.environ["ECS_CLUSTER"]
EXECUTION_ROLE_ARN = os.environ["ECS_EXECUTION_ROLE_ARN"]
SUBNET_IDS = os.environ["SUBNET_IDS"].split(",")
SECURITY_GROUP_ID = os.environ["SECURITY_GROUP_ID"]
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
    image_uri = body.get("image_uri")
    if not project_id or not image_uri:
        return _response(400, {"error": "project_id and image_uri are required"})

    service_name = f"svc-{project_id}"[:255]
    family = f"task-{project_id}"[:255]

    task_def = ecs.register_task_definition(
        family=family,
        requiresCompatibilities=["FARGATE"],
        networkMode="awsvpc",
        cpu="256",
        memory="512",
        executionRoleArn=EXECUTION_ROLE_ARN,
        containerDefinitions=[{
            "name": "app",
            "image": image_uri,
            "portMappings": [{"containerPort": 8080, "protocol": "tcp"}],
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": f"/ecs/{family}",
                    "awslogs-region": REGION,
                    "awslogs-create-group": "true",
                    "awslogs-stream-prefix": "app"
                }
            }
        }]
    )
    revision = task_def["taskDefinition"]["revision"]
    task_def_arn = task_def["taskDefinition"]["taskDefinitionArn"]

    existing = ecs.list_services(cluster=CLUSTER_NAME, launchType="FARGATE")
    service_exists = any(arn.endswith(f"/{service_name}") for arn in existing.get("serviceArns", []))

    network_config = {
        "awsvpcConfiguration": {
            "subnets": SUBNET_IDS,
            "securityGroups": [SECURITY_GROUP_ID],
            "assignPublicIp": "ENABLED"
        }
    }

    if service_exists:
        ecs.update_service(
            cluster=CLUSTER_NAME,
            service=service_name,
            taskDefinition=task_def_arn,
            desiredCount=1
        )
    else:
        ecs.create_service(
            cluster=CLUSTER_NAME,
            serviceName=service_name,
            taskDefinition=task_def_arn,
            desiredCount=1,
            launchType="FARGATE",
            networkConfiguration=network_config
        )

    deployment_id = f"{project_id}-{int(time.time())}"
    deployments_table.put_item(Item={
        "project_id": project_id,
        "deployment_id": deployment_id,
        "image_uri": image_uri,
        "task_definition_arn": task_def_arn,
        "revision": revision,
        "service_name": service_name,
        "status": "deployed",
        "deployed_at": int(time.time())
    })

    return _response(200, {
        "project_id": project_id,
        "deployment_id": deployment_id,
        "service_name": service_name,
        "revision": revision
    })


def _response(status, payload):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps(payload)
    }
