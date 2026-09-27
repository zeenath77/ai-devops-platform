resource "aws_ecr_repository" "generated_apps" {
  name                 = "${var.project_prefix}-generated-apps"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}
