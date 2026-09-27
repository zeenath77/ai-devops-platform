output "api_endpoint" {
  value = aws_apigatewayv2_api.http_api.api_endpoint
}

output "frontend_url" {
  value = "http://${aws_s3_bucket_website_configuration.frontend.website_endpoint}"
}

output "code_bucket" {
  value = aws_s3_bucket.code_bucket.bucket
}

output "ecr_repo_url" {
  value = aws_ecr_repository.generated_apps.repository_url
}

output "lambda_function_names" {
  value = { for k, v in aws_lambda_function.this : k => v.function_name }
}
