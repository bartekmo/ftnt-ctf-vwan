resource "azuread_administrative_unit" "example" {
  display_name              = "${var.prefix}-AU"
  description               = "AU for vwanlab resources (EMEA Cloud CSE team)"
  hidden_membership_enabled = false
}


resource "azurerm_user_assigned_identity" "ctf_app" {
  name                = "${var.prefix}-ctf-app"
  resource_group_name = azurerm_resource_group.infra.name
  location            = azurerm_resource_group.infra.location
}

# ── OIDC role assignments ──────────────────────────────────────────────────────

# Contributor on the resource group — uses the Managed Identity's principal_id
resource "azurerm_role_assignment" "github_actions_contributor" {
  scope                = azurerm_resource_group.infra.id
  role_definition_name = "Contributor"
  principal_id         = azurerm_user_assigned_identity.github_actions.principal_id
}

# AcrPush — lets Actions push newly built images to ACR
resource "azurerm_role_assignment" "github_actions_acr_push" {
  scope                = azurerm_container_registry.ctf.id
  role_definition_name = "AcrPush"
  principal_id         = azurerm_user_assigned_identity.github_actions.principal_id
}

resource "azurerm_role_assignment" "terraform_ctf_contributor" {
  scope                = azurerm_resource_group.infra.id
  role_definition_name = "Contributor"
  principal_id         = azurerm_user_assigned_identity.terraform_ctf.principal_id
}


resource "azurerm_role_assignment" "app_id_acr_pull" {
  scope                = azurerm_container_registry.ctf.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.ctf_app.principal_id
}

/*
resource "azurerm_role_assignment" "app_id_subscription_reader" {
  scope                = data.azurerm_subscription.current.id
  role_definition_name = "Reader"
  principal_id         = azurerm_user_assigned_identity.ctf_app.principal_id
}
*/
