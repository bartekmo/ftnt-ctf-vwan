terraform {
  required_version = ">= 1.7"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.110"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 2.53"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  cloud {
    organization = "40net"
    workspaces {
      name = "vwanlab-ctf"
    }
  }
}

provider "azurerm" {
  features {}
}

provider "azuread" {}

# ── Current context ───────────────────────────────────────────────────────

data "azurerm_client_config" "current" {}

# ── Resource group ────────────────────────────────────────────────────────

data "azurerm_resource_group" "ctf" {
  count = var.resource_group_name != null ? 1 : 0
  name  = var.resource_group_name
}

resource "azurerm_resource_group" "ctf" {
  count    = var.resource_group_name == null ? 1 : 0
  name     = "${var.prefix}-ctf"
  location = var.location
}

locals {
  ctf_rg = var.resource_group_name != null ? data.azurerm_resource_group.ctf[0] : azurerm_resource_group.ctf[0]
}

data "azurerm_subscription" "current" {
  subscription_id = var.azure_subscription_id
}

data "azurerm_user_assigned_identity" "app_id" {
  name                = var.app_id_name
  resource_group_name = local.ctf_rg.name
}
# ── Prober shared secret ──────────────────────────────────────────────────
# Generated once at first apply and stored in Terraform state.
# The same value is injected into both the API and prober containers.

resource "random_password" "prober_secret" {
  length  = 64
  special = false # hex-safe, no quoting issues in env vars
}

resource "random_password" "api_secret_key" {
  length  = 64
  special = false
}
