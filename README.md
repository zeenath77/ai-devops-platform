# AI DevOps Platform

Serverless CI/CD platform: describe an app in a prompt, AI generates it, the pipeline tests/scans/reviews/builds/deploys it to Fargate, and fixes itself on failure.

## What's actually implemented (real, working code — not stubs)

- **Prompt → Code Generation** — `backend/lambdas/code_generator` calls Gemini, writes generated files to S3, records the project in DynamoDB.
- **Prompt → Code Modification** — `code_modifier` loads a project's existing files from S3, sends a modification instruction to Gemini, writes back changed files.
- **AI Code Review** — `code_review` sends all project files to Gemini, parses an APPROVE / APPROVE_WITH_CHANGES / REJECT verdict.
- **Security Scanning** — `security_scan` does regex-based secret detection (AWS keys, hardcoded passwords/API keys, private keys) plus a Gemini summary of dependency files.
- **AI Root Cause / Failure Analysis** — `failure_analyzer` takes pipeline logs, returns structured JSON (failure type, root cause, suggested fix, confidence, is_transient).
- **AI Automatic Fix + Retry** — `auto_fix` takes the failing logs + current files, asks Gemini for corrected files, capped at `MAX_FIX_ATTEMPTS` (3).
- **Automated Deployment** — `deploy` registers a new ECS task definition and creates/updates a Fargate service per project, records the deployment in DynamoDB.
- **Rollback** — `rollback` looks up the previous deployment record and points the ECS service back at its task definition.
- **Deployment History / Pipeline Monitoring / Dashboard data** — `api` lambda serves projects, deployments, pipeline runs, and aggregate success-rate metrics over HTTP.
- **Serverless everything** — Lambda (compute), DynamoDB (data), S3 (generated code + static frontend hosting), API Gateway HTTP API, ECR + Fargate (running the generated apps) — no servers to manage.
- **CI/CD Pipeline** — `.github/workflows/ai-pipeline.yml` chains all of the above: security scan → code review → tests → Docker build → auto-fix loop on failure → deploy → rollback on failed deploy.
- **Dashboard** — `frontend/` is a plain HTML/JS page that calls the API Gateway endpoint: generate a project, see the project list, see pipeline runs and success-rate metrics.

## What you need to do before this runs end-to-end

This is a real scaffold, not a demo video — it needs the same setup work any new AWS project does:

1. **Terraform state bucket** — `backend.tf` expects an S3 bucket named `ai-devops-platform-tfstate`. Create it first (or change the name).
2. **Gemini API key** — get one from https://aistudio.google.com/apikey.
3. **Deploy the infra**:
   ```
   export GEMINI_API_KEY=your-key-here
   ./scripts/deploy.sh
   ```
4. **Wire the frontend to your API** — after `terraform output`, paste the `api_endpoint` value into `frontend/app.js`'s `API_URL`, then `aws s3 sync frontend/ s3://<frontend-bucket-name>/`.
5. **GitHub Actions secrets** — add `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` for an IAM identity that can invoke the `ai-devops-*` Lambdas, read/write the S3 code bucket, and push to ECR.
6. **Docker on the runner** — the pipeline's build step assumes Docker is available on the GitHub-hosted runner (it is, by default).

## Known limitations — be upfront about these in your report/demo

- **Generated apps are Python-only by default** (the generation prompt biases toward Flask/FastAPI). Other stacks aren't wired into the Docker build step.
- **Auto-fix retries are sequential Lambda calls inside one workflow run**, not a real Step Functions state machine — good enough to demonstrate the concept, not a production retry system.
- **No authentication** on the API Gateway endpoint or the dashboard — anyone with the URL can trigger generation (fine for a project demo, not for anything public).
- **Security scanning is pattern-based + an LLM summary**, not a real SAST tool like Semgrep/Bandit — accurately described as "AI-assisted" rather than "enterprise security scanning."
- **One ECS task per project**, no ALB/load balancing per generated app — you get a public IP per task, not a stable domain.
- Nothing here has been deployed and tested against live AWS yet — treat the first `terraform apply` as a real first run, not a rerun of something proven.

## Repo layout

```
backend/lambdas/<name>/lambda_function.py   — one Lambda per feature
backend/shared/gemini_client.py             — shared Gemini API helper
infra/terraform/                            — all AWS infra as code
frontend/                                   — static dashboard (S3-hosted)
.github/workflows/ai-pipeline.yml           — the orchestrated pipeline
scripts/deploy.sh                           — one-command Terraform apply
```
