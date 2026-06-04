terraform {
  #required_version = "1.15.5"

  cloud {
    organization = "40net"
    workspaces {
      name = "vwanlab-perm"
    }
  }

  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
    azuread = {
      source = "hashicorp/azuread"
    }
    github = {
      source = "integrations/github"
    }
    tfe = {
      source = "hashicorp/tfe"
    }
  }
}

provider "azurerm" {
  features {}
}

provider "azuread" {}

data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "infra" {
  name     = var.rg_name
  location = var.location

  lifecycle {
    prevent_destroy = true
    ignore_changes  = [tags]
  }
}

resource "azurerm_container_registry" "ctf" {
  name                = var.acr_name
  resource_group_name = azurerm_resource_group.infra.name
  location            = azurerm_resource_group.infra.location
  sku                 = "Basic"
  admin_enabled       = false
}

resource "github_actions_variable" "acr_login_server" {
  repository    = var.github_repo
  variable_name = "ACR_LOGIN_SERVER"
  value         = azurerm_container_registry.ctf.login_server
}

resource "github_actions_variable" "azure_resource_group" {
  repository    = var.github_repo
  variable_name = "AZURE_RESOURCE_GROUP"
  value         = azurerm_resource_group.infra.name
}

# Apply client ID to Terraform Cloud variable set
#

data "tfe_project" "vwanlab" {
  organization = var.tfc_org_name
  name         = var.tfc_project_name
}

data "tfe_workspace" "ctf" {
  organization = var.tfc_org_name
  name         = var.ctf_workspace_name
}

resource "tfe_variable_set" "acr" {
  organization      = var.tfc_org_name
  parent_project_id = data.tfe_project.vwanlab.id
  name              = "ACR registry for ctf"
}

resource "tfe_workspace_variable_set" "acr_for_ctf" {
  workspace_id    = data.tfe_workspace.ctf.id
  variable_set_id = tfe_variable_set.acr.id
}

resource "tfe_variable" "acr_id" {
  key             = "acr_id"
  value           = azurerm_container_registry.ctf.id
  category        = "terraform"
  variable_set_id = tfe_variable_set.acr.id
  sensitive       = false
}

resource "tfe_variable" "acr_name" {
  key             = "acr_name"
  value           = azurerm_container_registry.ctf.name
  category        = "terraform"
  variable_set_id = tfe_variable_set.acr.id
  sensitive       = false
}

resource "tfe_variable" "login_server" {
  key             = "acr_login_server"
  value           = azurerm_container_registry.ctf.login_server
  category        = "terraform"
  variable_set_id = tfe_variable_set.acr.id
  sensitive       = false
}

resource "tfe_variable" "app_id_name" {
  key          = "app_id_name"
  value        = azurerm_user_assigned_identity.ctf_app.name
  category     = "terraform"
  workspace_id = data.tfe_workspace.ctf.id
  sensitive    = false
}

resource "tfe_variable" "app_config_endpoint" {
  key          = "app_config_endpoint"
  value        = azurerm_app_configuration.ctf.endpoint
  category     = "terraform"
  workspace_id = data.tfe_workspace.ctf.id
  sensitive    = false
}

## App Configuration for CTF API settings
#
resource "azurerm_app_configuration" "ctf" {
  name                = "${var.prefix}-ctf-config"
  resource_group_name = azurerm_resource_group.infra.name
  location            = azurerm_resource_group.infra.location
  sku                 = "free" # free tier: 1000 req/day, plenty for config reads
}

# Grant the CTF app identity read access
resource "azurerm_role_assignment" "appconfig_reader" {
  scope                = azurerm_app_configuration.ctf.id
  role_definition_name = "App Configuration Data Reader"
  principal_id         = azurerm_user_assigned_identity.ctf_app.principal_id
}

resource "azurerm_role_assignment" "appconfig_data_owner" {
  scope                = azurerm_app_configuration.ctf.id
  role_definition_name = "App Configuration Data Owner"
  principal_id         = data.azurerm_client_config.current.object_id
}
