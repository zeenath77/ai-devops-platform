terraform {
  backend "s3" {
    bucket       = "ai-devops-platform-tfstate"
    key          = "platform/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
  }
}
