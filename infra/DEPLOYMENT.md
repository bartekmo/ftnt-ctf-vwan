# Deploying the CTF Platform on Azure

Target architecture: two **Azure Container Apps** — one for the API, one for the
frontend — backed by Azure Database for PostgreSQL Flexible Server. Images are
stored in Azure Container Registry (ACR) and rebuilt automatically by GitHub
Actions on every push to `main`.

## Authentication strategy: OIDC everywhere, no stored secrets

GitHub Actions uses **OpenID Connect (Workload Identity Federation)** to obtain
short-lived Azure tokens at runtime. This means:

- No `AZURE_CREDENTIALS` JSON blob stored in GitHub secrets
- No ACR username/password stored anywhere
- The token is valid only for the duration of a single workflow run
- Container Apps pulls images from ACR using its own **managed identity** —
  no registry credentials at runtime either

The only values stored in GitHub are non-sensitive **Variables** (not secrets):
`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`,
`AZURE_RESOURCE_GROUP`, `ACR_LOGIN_SERVER`.

OIDC is suitable for this use case because all workflow runs happen on
GitHub-hosted runners triggered by `push` to `main` or `workflow_dispatch` —
both are supported OIDC subjects. Self-hosted runners in isolated networks would
require a different approach.

---

## 1. Prerequisites

- Azure CLI installed and logged in (`az login`)
- Azure subscription with permissions to create resources and register app registrations
- GitHub repository: `bartekmo/ftnt-ctf-vwan`

Set shell variables used throughout:

```bash
RG=rg-xperts26-ctf
LOCATION=westeurope
ACR_NAME=xperts26ctf            # globally unique, lowercase, no hyphens
DB_SERVER=ctf-pg-xperts26
DB_USER=ctfadmin
DB_PASS=<strong-password>
DB_NAME=ctfdb
GITHUB_ORG=bartekmo
GITHUB_REPO=ftnt-ctf-vwan
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)
```

---

## 2. Create Azure Container Registry

ACR admin credentials are **not** used — Container Apps and GitHub Actions both
authenticate via managed/federated identity. The registry is created without
admin access.

```bash
az acr create \
  --resource-group $RG \
  --name $ACR_NAME \
  --sku Basic \
  --admin-enabled false

ACR_SERVER=$(az acr show --name $ACR_NAME --query loginServer -o tsv)
ACR_ID=$(az acr show --name $ACR_NAME --query id -o tsv)
echo "ACR_LOGIN_SERVER = $ACR_SERVER"
```

---

## 3. Create PostgreSQL Flexible Server

```bash
az postgres flexible-server create \
  --resource-group $RG \
  --name $DB_SERVER \
  --location $LOCATION \
  --admin-user $DB_USER \
  --admin-password $DB_PASS \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --version 16 \
  --database-name $DB_NAME \
  --public-access 0.0.0.0

DB_HOST=$(az postgres flexible-server show \
  --resource-group $RG --name $DB_SERVER \
  --query fullyQualifiedDomainName -o tsv)

echo "DB_HOST = $DB_HOST"
```

---

## 4. Create the service principal and configure OIDC federation

This SP is used only by GitHub Actions. It never holds a password that needs
rotating — federation replaces credential-based auth entirely.

```bash
# Create the app registration
APP_ID=$(az ad app create --display-name "github-ctf-deploy" --query appId -o tsv)
SP_ID=$(az ad sp create --id $APP_ID --query id -o tsv)

echo "AZURE_CLIENT_ID = $APP_ID"

# Grant Contributor on the resource group (enough for Container Apps updates)
az role assignment create \
  --assignee $SP_ID \
  --role Contributor \
  --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG

# Grant AcrPush on the registry (for image pushes from Actions)
az role assignment create \
  --assignee $SP_ID \
  --role AcrPush \
  --scope $ACR_ID

# Add federated credential — trusts pushes to main branch
az ad app federated-credential create \
  --id $APP_ID \
  --parameters '{
    "name": "github-main",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:'"$GITHUB_ORG"'/'"$GITHUB_REPO"':ref:refs/heads/main",
    "audiences": ["api://AzureADTokenExchange"]
  }'

# Add federated credential — trusts workflow_dispatch runs too
az ad app federated-credential create \
  --id $APP_ID \
  --parameters '{
    "name": "github-workflow-dispatch",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:'"$GITHUB_ORG"'/'"$GITHUB_REPO"':ref:refs/heads/main",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

---

## 5. Create the Container Apps environment

```bash
# Log Analytics workspace for Container Apps logs
az monitor log-analytics workspace create \
  --resource-group $RG \
  --workspace-name ctf-logs

LOG_WS_ID=$(az monitor log-analytics workspace show \
  -g $RG -n ctf-logs --query customerId -o tsv)
LOG_WS_KEY=$(az monitor log-analytics workspace get-shared-keys \
  -g $RG -n ctf-logs --query primarySharedKey -o tsv)

# Container Apps environment
az containerapp env create \
  --name ctf-env \
  --resource-group $RG \
  --location $LOCATION \
  --logs-workspace-id $LOG_WS_ID \
  --logs-workspace-key $LOG_WS_KEY
```

---

## 6. First image build and push

Before GitHub Actions is wired up, push the initial images manually.
Log in to ACR using your own Azure identity — no admin credentials needed.

```bash
az acr login --name $ACR_NAME

docker build -t $ACR_SERVER/ctf-api:latest ./backend
docker push $ACR_SERVER/ctf-api:latest

docker build -t $ACR_SERVER/ctf-frontend:latest ./frontend
docker push $ACR_SERVER/ctf-frontend:latest
```

---

## 7. Create the Container Apps

Each Container App gets a **system-assigned managed identity** which is granted
`AcrPull` on the registry. This is what pulls images at runtime — no stored
registry credentials anywhere.

### 7a. API

```bash
SECRET_KEY=$(openssl rand -hex 32)

az containerapp create \
  --name ctf-api \
  --resource-group $RG \
  --environment ctf-env \
  --image $ACR_SERVER/ctf-api:latest \
  --registry-server $ACR_SERVER \
  --system-assigned \
  --target-port 8000 \
  --ingress external \
  --cpu 1.0 --memory 2Gi \
  --min-replicas 1 --max-replicas 2 \
  --env-vars \
      ENVIRONMENT=production \
      CORS_ORIGINS=https://ctf-frontend.$(az containerapp env show -g $RG -n ctf-env --query properties.defaultDomain -o tsv) \
  --secrets \
      db-url="postgresql+asyncpg://$DB_USER:$DB_PASS@$DB_HOST:5432/$DB_NAME" \
      secret-key="$SECRET_KEY" \
  --env-vars \
      DATABASE_URL=secretref:db-url \
      SECRET_KEY=secretref:secret-key

# Grant the app's managed identity AcrPull
API_PRINCIPAL=$(az containerapp show -g $RG -n ctf-api \
  --query identity.principalId -o tsv)
az role assignment create \
  --assignee $API_PRINCIPAL \
  --role AcrPull \
  --scope $ACR_ID

API_FQDN=$(az containerapp show -g $RG -n ctf-api \
  --query properties.configuration.ingress.fqdn -o tsv)
echo "API URL: https://$API_FQDN"
```

### 7b. Frontend

```bash
az containerapp create \
  --name ctf-frontend \
  --resource-group $RG \
  --environment ctf-env \
  --image $ACR_SERVER/ctf-frontend:latest \
  --registry-server $ACR_SERVER \
  --system-assigned \
  --target-port 80 \
  --ingress external \
  --cpu 0.5 --memory 1Gi \
  --min-replicas 1 --max-replicas 2

FRONTEND_PRINCIPAL=$(az containerapp show -g $RG -n ctf-frontend \
  --query identity.principalId -o tsv)
az role assignment create \
  --assignee $FRONTEND_PRINCIPAL \
  --role AcrPull \
  --scope $ACR_ID

FRONTEND_FQDN=$(az containerapp show -g $RG -n ctf-frontend \
  --query properties.configuration.ingress.fqdn -o tsv)
echo "Frontend URL: https://$FRONTEND_FQDN"
```

> **Note:** After both apps are created, update the API's `CORS_ORIGINS` with the
> real frontend FQDN:
> ```bash
> az containerapp update -g $RG -n ctf-api \
>   --set-env-vars CORS_ORIGINS=https://$FRONTEND_FQDN
> ```

---

## 8. Seed the trainer account

```bash
curl -X POST "https://$API_FQDN/api/users/seed-trainer" \
  -G \
  --data-urlencode "username=trainer" \
  --data-urlencode "password=<your-trainer-password>" \
  --data-urlencode "email=trainer@xperts26.local"
```

---

## 9. Configure GitHub Actions variables

Go to **Settings → Secrets and variables → Actions → Variables** (not Secrets)
and add:

| Variable name          | Value | Why a variable, not a secret |
|------------------------|-------|------------------------------|
| `AZURE_CLIENT_ID`      | output of `echo $APP_ID` | Client IDs are not sensitive |
| `AZURE_TENANT_ID`      | output of `echo $TENANT_ID` | Tenant IDs are not sensitive |
| `AZURE_SUBSCRIPTION_ID`| output of `echo $SUBSCRIPTION_ID` | Not sensitive |
| `AZURE_RESOURCE_GROUP` | `rg-xperts26-ctf` | Not sensitive |
| `ACR_LOGIN_SERVER`     | output of `echo $ACR_SERVER` | Just a hostname |

No secrets are needed. The OIDC federation established in step 4 means GitHub
Actions proves its identity cryptographically — there is no credential to store.

---

## 10. How updates flow

```
git push origin main
       │
       ▼
GitHub Actions: build-push.yml
  ├── Requests short-lived Azure token via OIDC (no stored credentials)
  ├── Authenticates to ACR using that token
  ├── Builds only the image(s) whose source changed
  ├── Pushes  :<git-sha>  +  :latest  tags to ACR
  └── Runs: az containerapp update --image ...:$GITHUB_SHA
                   │
                   ▼
         Container Apps performs a rolling update:
         new revision starts, health-checked, then
         old revision drains — zero downtime
```

Container Apps uses **revisions** for updates. Each `az containerapp update`
creates a new revision. The old revision stays running until the new one passes
its health checks, giving zero-downtime deploys — a key advantage over ACI's
stop/start approach.

---

## 11. Rollback

Because each push creates a `:<git-sha>` tag and a named Container Apps
revision, rollback is non-destructive:

```bash
# List recent revisions
az containerapp revision list -g $RG -n ctf-api \
  --query "[].{name:name, created:properties.createdTime, active:properties.active}" \
  -o table

# Activate a previous revision (instant, no image pull needed)
az containerapp revision activate \
  -g $RG -n ctf-api \
  --revision <previous-revision-name>

# Or redeploy a specific git-sha image
az containerapp update -g $RG -n ctf-api \
  --image $ACR_SERVER/ctf-api:<previous-sha>
```

---

## 12. Quick-reference cheat sheet

```bash
# Stream live logs
az containerapp logs show -g $RG -n ctf-api   --follow
az containerapp logs show -g $RG -n ctf-frontend --follow

# Force redeploy current :latest (e.g. after config change)
az containerapp update -g $RG -n ctf-api      --image $ACR_SERVER/ctf-api:latest
az containerapp update -g $RG -n ctf-frontend --image $ACR_SERVER/ctf-frontend:latest

# Check revision status
az containerapp revision list -g $RG -n ctf-api -o table

# Update a secret (e.g. rotate SECRET_KEY)
az containerapp secret set -g $RG -n ctf-api \
  --secrets secret-key="$(openssl rand -hex 32)"
az containerapp update -g $RG -n ctf-api   # restart to pick up new secret

# Scale to zero outside event hours (cost saving)
az containerapp update -g $RG -n ctf-api      --min-replicas 0
az containerapp update -g $RG -n ctf-frontend --min-replicas 0
# Scale back up before the event
az containerapp update -g $RG -n ctf-api      --min-replicas 1
az containerapp update -g $RG -n ctf-frontend --min-replicas 1
```
