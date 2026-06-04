output "ctf_acr_id" {
  description = "The resource ID of the Azure Container Registry (ACR)."
  value       = azurerm_container_registry.ctf.id
}

output "ctf_acr_login_server" {
  description = "The login server URL of the Azure Container Registry (ACR), e.g. xperts26ctf.azurecr.io"
  value       = azurerm_container_registry.ctf.login_server
}

output "ctf_acr_name" {
  description = "The name of the Azure Container Registry (ACR)."
  value       = azurerm_container_registry.ctf.name
}



output "oidc_terraform_client_id" {
  description = "Client ID of the Azure AD application for Terraform Cloud OIDC authentication."
  value       = azurerm_user_assigned_identity.terraform_ctf.client_id
}

output "oidc_github_actions_client_id" {
  description = "Client ID of the Azure AD application for GitHub Actions OIDC authentication."
  value       = azurerm_user_assigned_identity.github_actions.client_id
}

output "app_config_endpoint" {
  value = azurerm_app_configuration.ctf.endpoint
}
