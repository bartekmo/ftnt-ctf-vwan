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

# Trusts workflow_dispatch runs on main (manual trigger from GitHub UI)
resource "azurerm_federated_identity_credential" "github_workflow_dispatch" {
  name                      = "${var.prefix}-infra-github-workflow-dispatch"
  audience                  = ["api://AzureADTokenExchange"]
  issuer                    = "https://token.actions.githubusercontent.com"
  user_assigned_identity_id = azurerm_user_assigned_identity.github_actions.id
  subject                   = "repo:${var.github_org}/${var.github_repo}:workflow_dispatch"
}

resource "azurerm_federated_identity_credential" "terraform_ctf" {
  for_each                  = toset(["plan", "apply"])
  name                      = "${var.prefix}-infra-terraformcloud-ctf-${each.key}"
  audience                  = ["api://AzureADTokenExchange"]
  issuer                    = "https://app.terraform.io"
  user_assigned_identity_id = azurerm_user_assigned_identity.terraform_ctf.id
  subject                   = "organization:40net:project:vwanlab:workspace:vwanlab-ctf:run_phase:${each.key}"
}


