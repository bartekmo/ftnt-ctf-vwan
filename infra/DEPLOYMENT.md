# Deploying the CTF Platform on Azure

Target architecture: two Azure Container Instances (ACI) — one for the API, one
for the frontend — backed by Azure Database for PostgreSQL Flexible Server.
Images are stored in Azure Container Registry (ACR) and rebuilt automatically by
GitHub Actions on every push to `main`.

---

## 1. Prerequisites

- Azure CLI installed and logged in (`az login`)
- A resource group already created, e.g. `rg-xperts26-ctf`
- GitHub repository: `bartekmo/ftnt-ctf-vwan`

Set shell variables you'll reuse throughout:

```bash
RG=rg-xperts26-ctf
LOCATION=westeurope
ACR_NAME=xperts26ctf          # must be globally unique, lowercase, no hyphens
ACR_SKU=Basic                 # Basic is enough for <10 images at workshop scale
DB_SERVER=ctf-pg-xperts26
DB_USER=ctfadmin
DB_PASS=<strong-password>     # set this to something real
DB_NAME=ctfdb
```

---

## 2. Create Azure Container Registry

```bash
az acr create \
  --resource-group $RG \
  --name $ACR_NAME \
  --sku $ACR_SKU \
  --admin-enabled true

# Save the login server (e.g. xperts26ctf.azurecr.io)
ACR_SERVER=$(az acr show --name $ACR_NAME --query loginServer -o tsv)
ACR_USER=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASS=$(az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv)

echo "ACR_LOGIN_SERVER = $ACR_SERVER"
echo "ACR_USERNAME     = $ACR_USER"
echo "ACR_PASSWORD     = $ACR_PASS"
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
  --public-access 0.0.0.0   # allow Azure services; lock down further if needed

DB_HOST=$(az postgres flexible-server show \
  --resource-group $RG --name $DB_SERVER \
  --query fullyQualifiedDomainName -o tsv)

echo "DATABASE_URL = postgresql+asyncpg://$DB_USER:$DB_PASS@$DB_HOST:5432/$DB_NAME"
```

---

## 4. Do the first image build locally and push

Before GitHub Actions is configured, push the initial images manually:

```bash
az acr login --name $ACR_NAME

# Backend
docker build -t $ACR_SERVER/ctf-api:latest ./backend
docker push $ACR_SERVER/ctf-api:latest

# Frontend
docker build -t $ACR_SERVER/ctf-frontend:latest ./frontend
docker push $ACR_SERVER/ctf-frontend:latest
```

---

## 5. Create the Container Instances

### 5a. API

```bash
SECRET_KEY=$(openssl rand -hex 32)

az container create \
  --resource-group $RG \
  --name ctf-api \
  --image $ACR_SERVER/ctf-api:latest \
  --registry-login-server $ACR_SERVER \
  --registry-username $ACR_USER \
  --registry-password $ACR_PASS \
  --cpu 1 --memory 1 \
  --ports 8000 \
  --ip-address Public \
  --dns-name-label ctf-api-xperts26 \
  --environment-variables \
      ENVIRONMENT=production \
      CORS_ORIGINS=https://ctf-frontend-xperts26.westeurope.azurecontainer.io \
  --secure-environment-variables \
      DATABASE_URL="postgresql+asyncpg://$DB_USER:$DB_PASS@$DB_HOST:5432/$DB_NAME" \
      SECRET_KEY="$SECRET_KEY"

API_FQDN=$(az container show -g $RG -n ctf-api \
  --query ipAddress.fqdn -o tsv)
echo "API FQDN: $API_FQDN"
```

### 5b. Frontend

```bash
az container create \
  --resource-group $RG \
  --name ctf-frontend \
  --image $ACR_SERVER/ctf-frontend:latest \
  --registry-login-server $ACR_SERVER \
  --registry-username $ACR_USER \
  --registry-password $ACR_PASS \
  --cpu 0.5 --memory 0.5 \
  --ports 80 \
  --ip-address Public \
  --dns-name-label ctf-frontend-xperts26
```

> **Note:** After creating the API container, update the frontend container with
> the real API FQDN in its nginx config — or use the DNS name directly from the
> frontend's nginx reverse proxy (already configured in `nginx.conf`).

---

## 6. Seed the trainer account

```bash
API_URL=https://$API_FQDN:8000   # or http:// if not behind TLS yet
curl -X POST "$API_URL/api/users/seed-trainer" \
  -G \
  --data-urlencode "username=trainer" \
  --data-urlencode "password=<your-trainer-password>" \
  --data-urlencode "email=trainer@xperts26.local"
```

---

## 7. Configure GitHub Actions secrets

In the GitHub repository go to **Settings → Secrets and variables → Actions**
and add the following secrets:

| Secret name            | Value |
|------------------------|-------|
| `ACR_LOGIN_SERVER`     | output of `echo $ACR_SERVER` — e.g. `xperts26ctf.azurecr.io` |
| `ACR_USERNAME`         | output of `echo $ACR_USER` |
| `ACR_PASSWORD`         | output of `echo $ACR_PASS` |
| `AZURE_RESOURCE_GROUP` | `rg-xperts26-ctf` |
| `AZURE_CREDENTIALS`    | JSON output of the service principal command below |

### Create a service principal for GitHub Actions

```bash
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

az ad sp create-for-rbac \
  --name "github-ctf-deploy" \
  --role Contributor \
  --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG \
  --sdk-auth
```

Copy the entire JSON output (including the outer `{}`) and paste it as the value
of the `AZURE_CREDENTIALS` secret.

---

## 8. How updates flow after setup

```
git push origin main
       │
       ▼
GitHub Actions: build-push.yml
  ├── Detects which paths changed (backend/ or frontend/)
  ├── Builds only the affected image(s)
  ├── Pushes  :latest  +  :<git-sha>  tags to ACR
  └── Runs:  az container restart --name ctf-api / ctf-frontend
                   │
                   ▼
         ACI pulls the new :latest image from ACR
         and restarts the container  (~30–60 seconds downtime)
```

The `:latest` tag is what ACI uses. The `:<git-sha>` tag gives you a permanent
record of every deployed build — useful for rolling back:

```bash
# Roll back API to a specific commit
az container delete -g $RG -n ctf-api --yes

az container create \
  --resource-group $RG \
  --name ctf-api \
  --image $ACR_SERVER/ctf-api:<previous-sha> \
  ... (same flags as step 5a)
```

---

## 9. Recommended improvements for production

| Concern | Recommendation |
|---------|----------------|
| TLS | Put an Application Gateway or Azure Front Door in front of both containers |
| Secrets | Move `SECRET_KEY` and DB password to Azure Key Vault; reference them in ACI via Key Vault integration |
| Zero-downtime deploys | Migrate from ACI to Azure Container Apps, which supports rolling updates |
| DB schema changes | Run `alembic upgrade head` as an init container before the API starts |
| Log visibility | Enable Azure Monitor / Log Analytics on both containers (`--log-analytics-workspace`) |
| ACR cleanup | Add an ACR retention policy to prune old `:<git-sha>` tags after 30 days |

---

## 10. Quick-reference cheat sheet

```bash
# View live API logs
az container logs -g $RG -n ctf-api --follow

# View live frontend logs
az container logs -g $RG -n ctf-frontend --follow

# Force redeploy latest image manually (same as what Actions does)
az container restart -g $RG -n ctf-api
az container restart -g $RG -n ctf-frontend

# Check container status
az container show -g $RG -n ctf-api --query "containers[0].instanceView.currentState"
```
