variable "aws_region" {
  default = "us-east-1"
}

variable "project_prefix" {
  default = "ai-devops"
}

variable "gemini_api_key" {
  type      = string
  sensitive = true
}
