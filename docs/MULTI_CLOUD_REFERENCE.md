# Multi-Cloud Reference Architecture

**No cloud deployment was executed for this POC.** Both reference architectures were
validated with `terraform fmt` and `terraform validate` only (see below for the exact
commands and results) — nothing under `infrastructure/` has ever been `apply`'d, and no
AWS or GCP account was touched.

## AWS architecture (`infrastructure/aws/`)

```
Internet --443--> ALB (public subnets) --container_port--> ECS Fargate tasks (private subnets)
                                                                    |
                                                                    v
                                                    RDS PostgreSQL 16 (private subnets, no public IP)
```

- **Compute**: ECS Fargate service + task definition, image pulled from a dedicated ECR
  repository (`image_scanning_configuration.scan_on_push=true`).
- **Database**: RDS PostgreSQL 16, `publicly_accessible=false`, `storage_encrypted=true`.
- **Secrets**: Secrets Manager holds the generated DB credentials; the ECS execution
  role's IAM policy grants `secretsmanager:GetSecretValue` on that one secret ARN only.
- **Logging**: CloudWatch Logs group per service, 30-day retention.
- **IAM**: execution role (image pull + log write + the one secret) and a task role
  that starts with **no** attached policies — the application makes no direct AWS SDK
  calls from domain/application code, so it needs none.
- **Network**: dedicated VPC, 2 AZs, public+private subnets, single NAT gateway (POC
  simplification — one per AZ for production). Three security groups (ALB, ECS tasks,
  RDS) wired so only the ALB accepts `0.0.0.0/0` traffic (443 only); ECS tasks accept
  traffic only from the ALB's security group; RDS accepts traffic only from the ECS
  tasks' security group. The ALB↔ECS cross-reference is expressed as standalone
  `aws_security_group_rule` resources rather than inline blocks, specifically to avoid
  a Terraform dependency cycle between the two groups.

## GCP architecture (`infrastructure/gcp/`)

```
Cloud Run v2 (direct VPC egress) --private IP--> Cloud SQL PostgreSQL 16
```

- **Compute**: Cloud Run v2 service, image from a dedicated Artifact Registry
  repository, with a `startup_probe` on `/health`.
- **Database**: Cloud SQL PostgreSQL 16 with `ipv4_enabled=false` — private IP only,
  reached via a `google_service_networking_connection` private-services-access peering
  (no Cloud SQL Auth Proxy sidecar needed).
- **Secrets**: Secret Manager holds the generated DB credentials; Cloud Run's env var
  references the secret directly (`value_source.secret_key_ref`), never a plaintext
  value.
- **IAM**: a dedicated Cloud Run service account with exactly four project-level roles:
  `secretmanager.secretAccessor` (scoped to the one secret), `logging.logWriter`,
  `monitoring.metricWriter`, `cloudsql.client`.
- **Access**: `var.allow_unauthenticated` (default `true` for local-demo convenience)
  controls whether `roles/run.invoker` is granted to `allUsers` — set to `false` and
  front with IAP/a load balancer for anything beyond a POC demo.

## Capability mapping

| Capability | AWS | GCP |
|---|---|---|
| Compute | ECS Fargate | Cloud Run v2 |
| Container registry | ECR | Artifact Registry |
| Managed PostgreSQL 16 | RDS | Cloud SQL |
| Secrets | Secrets Manager | Secret Manager |
| Logging | CloudWatch Logs | Cloud Logging (implicit via Cloud Run) |
| Least-privilege IAM | Execution/task role split | Dedicated service account, 4 scoped roles |
| Private DB access | VPC security groups | Private services access (VPC peering) |

## Portability boundaries

Application code has **no direct cloud SDK dependency** in `domain/` or
`application/` — the only cloud-shaped concept the app touches is a PostgreSQL
connection string and (optionally) an external AI provider's HTTP endpoint, both
provided via environment variables/secrets injected identically regardless of which
cloud is hosting it. Moving between AWS and GCP (or to the local Docker Compose
environment) requires no application code changes.

## Terraform validation method

Both directories were validated the same way, from a clean checkout:

```bash
cd infrastructure/aws   # or infrastructure/gcp
terraform fmt -recursive -check
terraform init -backend=false
terraform validate
```

Both returned `Success! The configuration is valid.` with no credentials configured
and no backend. `.terraform.lock.hcl` is committed for both directories for
reproducible provider version selection; `.terraform/` (the downloaded provider
binaries) is gitignored.

## Explicit statement

No `terraform plan` with real credentials and no `terraform apply` were run against
either AWS or GCP. No cloud resources exist as a result of this repository. The ACM
certificate ARN (AWS) and GCP project ID are placeholder values that must be replaced
before any real deployment could even be planned.
