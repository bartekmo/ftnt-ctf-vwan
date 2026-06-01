# ── URLs ─────────────────────────────────────────────────────────────────

output "api_url" {
  description = "HTTPS URL for the API."
  value       = "https://${azurerm_container_app.api.ingress[0].fqdn}"
}

output "frontend_url" {
  description = "HTTPS URL for the frontend (share this with attendees)."
  value       = "https://${azurerm_container_app.frontend.ingress[0].fqdn}"
}

output "acr_login_server" {
  description = "ACR login server hostname."
  value       = azurerm_container_registry.ctf.login_server
}

# ── GitHub Actions variables ──────────────────────────────────────────────
# Copy these values into:
#   GitHub repo → Settings → Secrets and variables → Actions → Variables

output "github_actions_variables" {
  description = "Paste these into GitHub Actions Variables (not Secrets)."
  value = {
    AZURE_CLIENT_ID       = azuread_application.github_actions.client_id
    AZURE_TENANT_ID       = data.azurerm_client_config.current.tenant_id
    AZURE_SUBSCRIPTION_ID = data.azurerm_client_config.current.subscription_id
    AZURE_RESOURCE_GROUP  = local.ctf_rg.name
    ACR_LOGIN_SERVER      = azurerm_container_registry.ctf.login_server
  }
}

# ── Trainer seed command ──────────────────────────────────────────────────

output "seed_trainer_command" {
  description = "Run this after first deploy to create the trainer account."
  value       = <<-CMD
    curl -X POST "https://${azurerm_container_app.api.ingress[0].fqdn}/api/users/seed-trainer" \
      -G \
      --data-urlencode "username=trainer" \
      --data-urlencode "password=<your-trainer-password>" \
      --data-urlencode "email=trainer@xperts26.local"
  CMD
}

# ── First push commands ───────────────────────────────────────────────────

output "first_push_commands" {
  description = "Run these once after terraform apply to push initial images before GitHub Actions is triggered."
  value       = <<-CMD
    az acr login --name ${azurerm_container_registry.ctf.name}
    docker build -t ${azurerm_container_registry.ctf.login_server}/ctf-api:latest ./backend && \
    docker push ${azurerm_container_registry.ctf.login_server}/ctf-api:latest
    docker build -t ${azurerm_container_registry.ctf.login_server}/ctf-frontend:latest ./frontend && \
    docker push ${azurerm_container_registry.ctf.login_server}/ctf-frontend:latest
  CMD
}
