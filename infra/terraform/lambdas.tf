locals {
  lambdas = {
    code_generator    = { handler = "lambda_function.lambda_handler", timeout = 60 }
    code_modifier     = { handler = "lambda_function.lambda_handler", timeout = 60 }
    code_review       = { handler = "lambda_function.lambda_handler", timeout = 60 }
    security_scan     = { handler = "lambda_function.lambda_handler", timeout = 60 }
    failure_analyzer  = { handler = "lambda_function.lambda_handler", timeout = 45 }
    auto_fix          = { handler = "lambda_function.lambda_handler", timeout = 60 }
    deploy            = { handler = "lambda_function.lambda_handler", timeout = 90 }
    rollback          = { handler = "lambda_function.lambda_handler", timeout = 60 }
    api               = { handler = "lambda_function.lambda_handler", timeout = 15 }
  }

  common_env = {
    CODE_BUCKET         = aws_s3_bucket.code_bucket.bucket
    PROJECTS_TABLE      = aws_dynamodb_table.projects.name
    DEPLOYMENTS_TABLE   = aws_dynamodb_table.deployments.name
    PIPELINE_RUNS_TABLE = aws_dynamodb_table.pipeline_runs.name
    GEMINI_SECRET_NAME  = aws_secretsmanager_secret.gemini_api_key.name
    ECS_CLUSTER         = aws_ecs_cluster.main.name
    ECS_EXECUTION_ROLE_ARN = aws_iam_role.ecs_execution.arn
    SUBNET_IDS          = join(",", data.aws_subnets.default.ids)
    SECURITY_GROUP_ID   = aws_security_group.ecs_tasks.id
    PROJECT_PREFIX      = var.project_prefix
  }
}

data "archive_file" "lambda_zip" {
  for_each    = local.lambdas
  type        = "zip"
  source_dir  = "${path.module}/../../backend/lambdas/${each.key}"
  output_path = "${path.module}/build/${each.key}.zip"
}

resource "aws_lambda_function" "this" {
  for_each         = local.lambdas
  function_name    = "${var.project_prefix}-${replace(each.key, "_", "-")}"
  role             = aws_iam_role.lambda_exec.arn
  handler          = each.value.handler
  runtime          = "python3.12"
  timeout          = each.value.timeout
  memory_size      = 512
  filename         = data.archive_file.lambda_zip[each.key].output_path
  source_code_hash = data.archive_file.lambda_zip[each.key].output_base64sha256

  environment {
    variables = local.common_env
  }
}
