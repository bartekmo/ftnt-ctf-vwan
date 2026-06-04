# Create the User-Assigned Managed Identity (Replaces App Registration & SP)
resource "azurerm_user_assigned_identity" "github_actions" {
  name                = "${var.prefix}-infra-github-actions"
  resource_group_name = azurerm_resource_group.infra.name
  location            = azurerm_resource_group.infra.location
}

resource "azurerm_user_assigned_identity" "terraform_ctf" {
  name                = "${var.prefix}-infra-terraform-ctf"
  resource_group_name = azurerm_resource_group.infra.name
  location            = azurerm_resource_group.infra.location
}

# ── Federated credentials ─────────────────────────────────────────────────

# Trusts workflow runs triggered by a push to main
resource "azurerm_federated_identity_credential" "github_push_main" {
  name                      = "${var.prefix}-infra-github-push-main"
  audience                  = ["api://AzureADTokenExchange"]
  issuer                    = "https://token.actions.githubusercontent.com"
  user_assigned_identity_id = azurerm_user_assigned_identity.github_actions.id
  subject                   = "repo:${var.github_org}/${var.github_repo}:ref:refs/heads/main"
}

resource "azurerm_federated_identity_credential" "terraform_ctf" {
  for_each                  = toset(["plan", "apply"])
  name                      = "${var.prefix}-infra-terraformcloud-ctf-${each.key}"
  audience                  = ["api://AzureADTokenExchange"]
  issuer                    = "https://app.terraform.io"
  user_assigned_identity_id = azurerm_user_assigned_identity.terraform_ctf.id
  subject                   = "organization:40net:project:vwanlab:workspace:vwanlab-ctf:run_phase:${each.key}"
}

# Apply client ID to Terraform Cloud variable set
#
data "tfe_variable_set" "vwanlab_ctf_oidc" {
  organization      = "40net"
  parent_project_id = "vwanlab"
  name              = "Azure OIDC terraform-ctf"
}

resource "tfe_variable" "azure_oidc_terraform_client_id" {
  key             = "TFC_AZURE_RUN_CLIENT_ID"
  value           = azurerm_user_assigned_identity.terraform_ctf.client_id
  category        = "env"
  variable_set_id = data.tfe_variable_set.vwanlab_ctf_oidc.id
  sensitive       = false
}

# Apply client ID to GitHub Actions secrets
#
resource "github_actions_secret" "azure_oidc_github_client_id" {
  repository  = var.github_repo
  secret_name = "AZURE_CLIENT_ID"
  value       = azurerm_user_assigned_identity.github_actions.client_id
}

