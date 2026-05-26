# GitHub Actions OIDC / Workload Identity Federation
#
# Creates an Azure AD app registration with two federated credentials:
#   1. push to main branch
#   2. workflow_dispatch on main branch
#
# No client secret is created — GitHub proves its identity by presenting a
# short-lived JWT signed by GitHub's OIDC provider. Azure AD verifies the
# signature against the well-known OIDC metadata endpoint and issues a
# short-lived access token scoped to the requested resource.
#
# Role assignments:
#   - Contributor on the resource group  (needed to update Container Apps)
#   - AcrPush on the registry            (needed to push built images)

# ── App registration ──────────────────────────────────────────────────────

resource "azuread_application" "github_actions" {
  display_name = "github-ctf-deploy"
}

resource "azuread_service_principal" "github_actions" {
  client_id = azuread_application.github_actions.client_id
}

# ── Federated credentials ─────────────────────────────────────────────────

# Trusts workflow runs triggered by a push to main
resource "azuread_application_federated_identity_credential" "github_push_main" {
  application_id = azuread_application.github_actions.id
  display_name   = "github-push-main"
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_org}/${var.github_repo}:ref:refs/heads/main"
  audiences      = ["api://AzureADTokenExchange"]
  description    = "Trusts GitHub Actions push-to-main runs for ${var.github_org}/${var.github_repo}"
}

# Trusts workflow_dispatch runs on main (manual trigger from GitHub UI)
resource "azuread_application_federated_identity_credential" "github_workflow_dispatch" {
  application_id = azuread_application.github_actions.id
  display_name   = "github-workflow-dispatch"
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_org}/${var.github_repo}:workflow_dispatch"
  audiences      = ["api://AzureADTokenExchange"]
  description    = "Trusts manual workflow_dispatch runs for ${var.github_org}/${var.github_repo}"
}

# ── Role assignments ──────────────────────────────────────────────────────

# Contributor on the resource group — lets Actions call az containerapp update
resource "azurerm_role_assignment" "github_actions_contributor" {
  scope                = azurerm_resource_group.ctf.id
  role_definition_name = "Contributor"
  principal_id         = azuread_service_principal.github_actions.object_id
}

# AcrPush — lets Actions push newly built images to ACR
resource "azurerm_role_assignment" "github_actions_acr_push" {
  scope                = azurerm_container_registry.ctf.id
  role_definition_name = "AcrPush"
  principal_id         = azuread_service_principal.github_actions.object_id
}
