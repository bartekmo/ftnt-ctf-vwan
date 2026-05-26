# Terraform — CTF Platform on Azure

Provisions the full CTF platform infrastructure matching `infra/DEPLOYMENT.md`.

## What this creates

| Resource | Purpose |
|----------|---------|
| Resource Group | Container for all resources |
| Azure Container Registry | Stores `ctf-api` and `ctf-frontend` images |
| PostgreSQL Flexible Server 16 | Application database (Burstable B1ms) |
| Log Analytics Workspace | Logs for Container Apps |
| Container Apps Environment | Shared runtime for both apps |
| Container App: `ctf-api` | FastAPI backend, port 8000, system-assigned MI |
| Container App: `ctf-frontend` | Nginx + React, port 80, system-assigned MI |
| Role: AcrPull (×2) | Grants each Container App MI pull access to ACR |
| Azure AD App Registration | Identity for GitHub Actions OIDC |
| Service Principal | Azure identity backed by the app registration |
| Federated Credential: push | Trusts `push` to `main` from GitHub Actions |
| Federated Credential: dispatch | Trusts `workflow_dispatch` from GitHub Actions |
| Role: Contributor on RG | Allows Actions to update Container Apps |
| Role: AcrPush on ACR | Allows Actions to push images |

## Prerequisites

- Terraform >= 1.7
- Azure CLI logged in (`az login`) with permission to create resources and
  register Azure AD applications
- Docker (for the initial image push)

## Usage

```bash
cd infra/terraform

# 1. Copy and fill in variables
cp terraform.tfvars.example terraform.tfvars
$EDITOR terraform.tfvars

# 2. Initialise providers
terraform init

# 3. Preview changes
terraform plan

# 4. Apply
terraform apply

# 5. Push initial images (output by terraform apply)
terraform output -raw first_push_commands | bash

# 6. Set GitHub Actions variables (output by terraform apply)
terraform output github_actions_variables

# 7. Seed the trainer account
terraform output -raw seed_trainer_command
# (then run the printed curl command with a real trainer password)
```

## Chicken-and-egg: images vs Container Apps

Terraform creates the Container Apps pointing at the image tags specified in
`var.api_image` / `var.frontend_image`. If those images don't exist in ACR yet,
the Container Apps will enter a failed state on first deploy.

**Recommended order:**
1. `terraform apply` — creates ACR and all other resources; Container Apps may
   show a pull error initially
2. Run the `first_push_commands` output to push `:latest` images
3. `terraform apply` again (or `az containerapp update`) — Container Apps will
   now start successfully

Alternatively, set `min_replicas = 0` in `container_apps.tf` before the first
apply so the apps don't try to start until images are available.

## Destroying

```bash
terraform destroy
```

This removes all Azure resources. The Azure AD app registration is also removed.
The GitHub Actions variables in the repo must be deleted manually.
