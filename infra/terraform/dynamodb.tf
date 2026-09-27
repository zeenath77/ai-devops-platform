resource "aws_dynamodb_table" "projects" {
  name         = "${var.project_prefix}-projects"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "project_id"

  attribute {
    name = "project_id"
    type = "S"
  }
}

resource "aws_dynamodb_table" "deployments" {
  name         = "${var.project_prefix}-deployments"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "project_id"
  range_key    = "deployment_id"

  attribute {
    name = "project_id"
    type = "S"
  }

  attribute {
    name = "deployment_id"
    type = "S"
  }
}

resource "aws_dynamodb_table" "pipeline_runs" {
  name         = "${var.project_prefix}-pipeline-runs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "project_id"
  range_key    = "run_id"

  attribute {
    name = "project_id"
    type = "S"
  }

  attribute {
    name = "run_id"
    type = "S"
  }
}
